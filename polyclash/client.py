import sys
import numpy as np
import pyvista as pv
import colorsys
import os.path as osp

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QBrush
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget

from pyvistaqt import QtInteractor
from vtkmodules.vtkCommonCore import vtkCommand

from polyclash.board import Board, BLACK
from polyclash.data import cities, triangles, pentagons, triangle2faces, pentagon2faces, city_manager


# Load the VTK format 3D model
model_path = osp.abspath(osp.join(osp.dirname(__file__), "board.vtk"))
mesh = pv.read(model_path)


# Define colors for different purposes
group_colors = {
    0: (0.85, 0.75, 0.60, 1.0),  # Warm earth tone
    1: (0.45, 0.85, 0.45, 1.0),  # Brighter green
    2: (0.80, 0.75, 0.45, 1.0),  # Softer gold with a touch of green
    3: (0.55, 0.60, 0.85, 1.0),  # Soft purple
}
sea_color = (0.3, 0.5, 0.7, 1.0)  # Ocean blue
city_color = (0.5, 0.5, 0.5, 1.0)  # City marker color
font_color = (0.2, 0.2, 0.2, 1.0)  # Text color


# Create a board and a city manager
board = Board()

overlay = None


# Pick event handling
class CustomInteractor(QtInteractor):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.picker = self.interactor.GetRenderWindow().GetInteractor().CreateDefaultPicker()
        self.interactor.AddObserver(vtkCommand.LeftButtonPressEvent, self.left_button_press_event)

    def left_button_press_event(self, obj, event):

        click_pos = self.interactor.GetEventPosition()
        self.picker.Pick(click_pos[0], click_pos[1], 0, self.renderer)

        picked_actor = self.picker.GetActor()
        if picked_actor:
            center = picked_actor.GetCenter()
            position = np.array([center[0], center[1], center[2]])

            nearest_city = city_manager.find_nearest_city(position)
            if board.current_player == BLACK:
                picked_actor.GetProperty().SetColor(0, 0, 0)
                if overlay:
                    overlay.change_color(Qt.white)
            else:
                picked_actor.GetProperty().SetColor(1, 1, 1)
                if overlay:
                    overlay.change_color(Qt.black)
            board.play(nearest_city, board.current_player)
            board.current_player = -board.current_player

        self.interactor.GetRenderWindow().Render()
        return


class Overlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = Qt.black  # set default color
        self.setAttribute(Qt.WA_TranslucentBackground)  # set transparent background

    def paintEvent(self, event):
        painter = QPainter(self)

        # set opacity
        painter.setOpacity(0.5)  # 50% transparent

        # 绘制半透明背景
        painter.setBrush(QBrush(QColor(192, 192, 192, 127)))  # 浅灰色，半透明
        painter.drawRect(self.rect())  # 覆盖整个Widget区域

        # 绘制小圆盘，不透明
        painter.setOpacity(1.0)  # 重置为不透明
        painter.setBrush(QBrush(self.color))
        painter.drawEllipse(10, 10, 50, 50)  # 绘制小圆盘

    def change_color(self, color):
        self.color = color
        self.update()  # 更新Widget，触发重绘


# Main window
class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.face_colors = None
        self.spheres = {}
        self.setWindowTitle("Polyclash")

        self.overlay = Overlay(self)
        self.overlay.setGeometry(700, 20, 210, 240)

        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

        self.frame = QtWidgets.QFrame()
        self.layout = QtWidgets.QGridLayout()

        self.vtk_widget = CustomInteractor(self.frame)
        self.layout.addWidget(self.vtk_widget, 0, 0, 1, 2)

        self.frame.setLayout(self.layout)
        self.setCentralWidget(self.frame)

        self.init_color()
        self.init_pyvista(cities)
        self.update_overlay_position()
        self.overlay.raise_()

    def update_overlay_position(self):
        overlay_width = 210
        overlay_height = 240
        self.overlay.setGeometry(self.width() - overlay_width - 20, 20, overlay_width, overlay_height)

    def resizeEvent(self, event):
        self.update_overlay_position()
        super().resizeEvent(event)

    def adjust_hue(self, rgb_color, adjustment_factor):
        # convert RGB to HSV
        hsv_color = colorsys.rgb_to_hsv(*rgb_color[:3])
        # adjust hue, make sure the result is in [0, 1]
        new_hue = (hsv_color[0] + adjustment_factor) % 1.0
        # convert HSV as RGB
        adjusted_rgb = colorsys.hsv_to_rgb(new_hue, hsv_color[1], hsv_color[2])
        return adjusted_rgb + (rgb_color[3],)

    def init_color(self):
        # Initialize the color array for all faces
        face_colors = np.ones((mesh.n_cells, 4))

        for i, triangle in enumerate(triangles):
            face = triangle
            groups = [vertex // 15 for vertex in face]
            # If all vertices are from the same group, color the face accordingly
            if len(set(groups)) == 1:
                for j in range(3):
                    face_colors[triangle2faces[i][j]] = group_colors[groups[0]]
            else:
                # Default to sea color for mixed groups
                for j in range(3):
                    face_colors[triangle2faces[i][j]] = sea_color

        for i, pentagon in enumerate(pentagons):
            face = pentagon
            groups = [vertex // 15 for vertex in face]
            # If all vertices are from the same group, color the face accordingly
            if len(set(groups)) == 1:
                for j in range(5):
                    face_colors[pentagon2faces[i][j]] = group_colors[groups[0]]

        # Set the color data to the mesh object
        mesh.cell_data['colors'] = face_colors
        self.face_colors = face_colors

    def init_pyvista(self, cities=None):
        self.vtk_widget.set_background("darkgray")
        self.vtk_widget.add_mesh(mesh, show_edges=True, color="lightblue", pickable=False, scalars=self.face_colors, rgba=True)
        # self.vtk_widget.add_point_labels(cities[:60], range(60), point_color=city_color, point_size=10,
        #                         render_points_as_spheres=True, text_color=font_color, font_size=80, shape_opacity=0.0)

        for idx, city in enumerate(cities):
            self.vtk_widget.show_axes = True
            self.vtk_widget.add_axes(interactive=True)
            sphere = pv.Sphere(radius=0.02, center=city)
            actor = self.vtk_widget.add_mesh(sphere, color=city_color, pickable=True)
            self.spheres[idx] = actor

    def remove_stone(self, point):
        actor = self.spheres[point]
        actor.GetProperty().SetColor(city_color[0], city_color[1], city_color[2])

    def handle(self, message, **kwargs):
        if message == "remove_stones":
            self.remove_stone(kwargs["point"])
        self.vtk_widget.render()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1600, 1200)
    overlay = window.overlay
    board.register_observer(window)

    screen = app.primaryScreen().geometry()
    x = (screen.width() - window.width()) / 2
    y = (screen.height() - window.height()) / 2
    window.move(int(x), int(y))

    window.show()
    sys.exit(app.exec_())

