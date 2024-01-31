from time import sleep
from typing import Tuple, List
from dataclasses import dataclass, field
from threading import Thread
from signal import signal, SIGINT

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

import pygame
import numpy as np

from pysocialforce.map_config import Obstacle
from pysocialforce.simulator import SimState

Vec2D = Tuple[float, float]
RobotPose = Tuple[Vec2D, float]
RobotAction = Tuple[float, float]
RgbColor = Tuple[int, int, int]


BACKGROUND_COLOR = (255, 255, 255)
BACKGROUND_COLOR_TRANSP = (255, 255, 255, 128)
OBSTACLE_COLOR = (20, 30, 20, 128)
PED_COLOR = (255, 50, 50)
PED_ACTION_COLOR = (255, 50, 50)
TEXT_COLOR = (0, 0, 0)


@dataclass
class VisualizableSimState:
    """Representing a collection of properties to display
    the simulator's state at a discrete timestep."""
    timestep: int
    pedestrian_positions: np.ndarray
    ped_actions: np.ndarray


def to_visualizable_state(step: int, sim_state: SimState) -> VisualizableSimState:
    state, groups = sim_state
    ped_pos = np.array(state[:, 0:2])
    ped_vel = np.array(state[:, 2:4])
    actions = np.concatenate((
            np.expand_dims(ped_pos, axis=1),
            np.expand_dims(ped_pos + ped_vel, axis=1)
        ), axis=1)
    return VisualizableSimState(step, ped_pos, actions)


@dataclass
class SimulationView:
    width: float=1200
    height: float=800
    scaling: float=15
    ped_radius: float=0.4
    obstacles: List[Obstacle] = field(default_factory=list)
    size_changed: bool = field(init=False, default=False)
    is_exit_requested: bool = field(init=False, default=False)
    is_abortion_requested: bool = field(init=False, default=False)
    screen: pygame.surface.Surface = field(init=False)
    font: pygame.font.Font = field(init=False)
    redraw_needed: bool = field(init=False, default=False)
    offset: np.array = field(init=False, default=np.array([0, 0]))

    @property
    def timestep_text_pos(self) -> Vec2D:
        return (10, 10)

    def __post_init__(self):
        pygame.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode(
            (self.width, self.height), pygame.RESIZABLE)
        pygame.display.set_caption('RobotSF Simulation')
        self.font = pygame.font.SysFont('Consolas', 14)
        self.surface_obstacles = self.preprocess_obstacles()
        self.clear()

    def preprocess_obstacles(self) -> pygame.Surface:
        obst_vertices = [o.vertices_np * self.scaling for o in self.obstacles]
        min_x, max_x, min_y, max_y = 0, -np.inf, 0, -np.inf
        for vertices in obst_vertices:
            min_x, max_x = min(np.min(vertices[:, 0]), min_x), max(np.max(vertices[:, 0]), max_x)
            min_y, max_y = min(np.min(vertices[:, 1]), min_y), max(np.max(vertices[:, 1]), max_y)
        width, height = max_x - min_x, max_y - min_y
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        surface.fill(BACKGROUND_COLOR_TRANSP)
        for vertices in obst_vertices:
            pygame.draw.polygon(surface, OBSTACLE_COLOR, [(x, y) for x, y in vertices])
        return surface

    def show(self):
        self.ui_events_thread = Thread(target=self._process_event_queue)
        self.ui_events_thread.start()

        def handle_sigint(signum, frame):
            self.is_exit_requested = True
            self.is_abortion_requested = True

        signal(SIGINT, handle_sigint)

    def exit(self):
        self.is_exit_requested = True
        self.ui_events_thread.join()

    def _process_event_queue(self):
        while not self.is_exit_requested:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.is_exit_requested = True
                    self.is_abortion_requested = True
                elif e.type == pygame.VIDEORESIZE:
                    self.size_changed = True
                    self.width, self.height = e.w, e.h
                elif e.type == pygame.KEYDOWN:
                    # handle key presses
                    if e.key == pygame.K_PLUS:
                        self.scaling += 1
                        self.redraw_needed = True
                    elif e.key == pygame.K_MINUS:
                        self.scaling -= 1
                        if self.scaling < 1:
                            # prevent scaling from going below 1
                            self.scaling = 1
                        self.redraw_needed = True
                    elif e.key == pygame.K_LEFT:
                        self.offset[0] -= 10
                    elif e.key == pygame.K_RIGHT:
                        self.offset[0] += 10
                    elif e.key == pygame.K_UP:
                        self.offset[1] -= 10
                    elif e.key == pygame.K_DOWN:
                        self.offset[1] += 10
            sleep(0.01)

    def clear(self):
        self.screen.fill(BACKGROUND_COLOR)
        self._add_text(0)
        pygame.display.update()

    def render(self, state: VisualizableSimState, fps: int=60):
        sleep(1 / fps)
        # info: event handling needs to be processed
        #       in the main thread to access UI resources
        if self.is_exit_requested:
            pygame.quit()
            self.ui_events_thread.join()
            if self.is_abortion_requested:
                exit()
        if self.size_changed:
            self._resize_window()
            self.size_changed = False
        if self.redraw_needed:
            self.surface_obstacles = self.preprocess_obstacles()
            self.redraw_needed = False
        state = self._scale_pedestrian_state(state)
        self.screen.fill(BACKGROUND_COLOR)
        self._draw_obstacles()
        self._draw_grid()
        self._augment_ped_actions(state.ped_actions)
        self._draw_pedestrians(state.pedestrian_positions)
        self._add_text(state.timestep)
        pygame.display.update()

    def _resize_window(self):
        old_surface = self.screen
        self.screen = pygame.display.set_mode(
            (self.width, self.height), pygame.RESIZABLE)
        self.screen.blit(old_surface, (0, 0))

    def _scale_pedestrian_state(self, state: VisualizableSimState) \
            -> Tuple[VisualizableSimState, Tuple[float, float]]:
        state.pedestrian_positions *= self.scaling
        state.ped_actions *= self.scaling
        return state

    def _draw_pedestrians(self, ped_pos: np.ndarray):
        for ped_x, ped_y in ped_pos:
            pygame.draw.circle(
                self.screen,
                PED_COLOR,
                (ped_x+self.offset[0], ped_y+self.offset[1]),
                self.ped_radius * self.scaling
                )

    def _draw_obstacles(self):
        self.screen.blit(self.surface_obstacles, self.offset)

    def _augment_ped_actions(self, ped_actions: np.ndarray):
        """Draw the actions of the pedestrians as lines."""
        for p1, p2 in ped_actions:
            pygame.draw.line(
                self.screen,
                PED_ACTION_COLOR,
                p1+self.offset,
                p2+self.offset,
                width=3
                )

    def _add_text(self, timestep: int):
        text_lines = [
            f'step: {timestep}',
            f'offset: {self.offset[0]}, {self.offset[1]}',
            f'scaling: {self.scaling}'
        ]
        for i, text in enumerate(text_lines):
            text_surface = self.font.render(text, False, TEXT_COLOR)
            pos = self.timestep_text_pos[0], self.timestep_text_pos[1] + i * self.font.get_linesize()
            self.screen.blit(text_surface, pos)

    def _draw_grid(
            self,
            grid_increment: int=50,
            grid_color: RgbColor=(200, 200, 200)
            ):
        """
        Draw a grid on the screen.
        :param grid_increment: The increment of the grid in pixels.
        :param grid_color: The color of the grid lines.
        """
        scaled_grid_size = grid_increment*self.scaling
        font = pygame.font.Font(None, 24)
        # draw the vertical lines
        for x in range(self.offset[0], self.width+self.offset[0], scaled_grid_size):
            pygame.draw.line(
                self.screen,
                grid_color,
                (x, 0),
                (x, self.height)
                )
            label = font.render(str(int((x-self.offset[0])/self.scaling)), 1, grid_color)
            self.screen.blit(label, (x, 0))
        
        # draw the horizontal lines
        for y in range(0, self.height, scaled_grid_size):
            adjusted_y = y + self.offset[1]  # adjust y by the offset
            pygame.draw.line(self.screen, grid_color, (0, adjusted_y), (self.width, adjusted_y))
            label = font.render(str(int(y/self.scaling)), 1, grid_color)
            self.screen.blit(label, (0, adjusted_y))  # use adjusted_y here
