"""This module tracks the state of scene and scene elements
like pedestrians, groups and obstacles"""

from math import cos, sin, atan2, pi
from typing import List, Tuple
from dataclasses import dataclass, field

import numpy as np

from pysocialforce.config import SceneConfig


Line2D = Tuple[float, float, float, float]
Point2D = Tuple[float, float]
Group = List[int]


class PedState:
    """Tracks the state of pedstrains and social groups"""

    def __init__(self, state: np.ndarray, groups: List[Group], config: SceneConfig):
        self.default_tau = config.tau
        self.d_t = config.dt_secs
        self.agent_radius = config.agent_radius
        self.max_speed_multiplier = config.max_speed_multiplier

        self.max_speeds = None
        self.initial_speeds = None
        self.update(state, groups)

    def update(self, state: np.ndarray, groups: List[List[int]]):
        self.state = state
        self.groups = groups

    def _update_state(self, state: np.ndarray):
        tau = np.full((state.shape[0]), self.default_tau)
        if state.shape[1] < 7:
            self._state = np.concatenate((state, np.expand_dims(tau, -1)), axis=-1)
        else:
            self._state = state
        if self.initial_speeds is None:
            self.initial_speeds = self.speeds()
        self.max_speeds = self.max_speed_multiplier * self.initial_speeds

    @property
    def state(self) -> np.ndarray:
        return self._state

    @state.setter
    def state(self, state: np.ndarray):
        self._update_state(state)

    def get_states(self):
        return np.array([self.state]), [self.groups]

    def size(self) -> int:
        return self.state.shape[0]

    def pos(self) -> np.ndarray:
        return self.state[:, 0:2]

    def vel(self) -> np.ndarray:
        return self.state[:, 2:4]

    def goal(self) -> np.ndarray:
        return self.state[:, 4:6]

    def tau(self):
        return self.state[:, 6:7]

    def speeds(self):
        """Return the speeds corresponding to a given state."""
        return np.linalg.norm(self.vel(), axis=1)

    def step(self, force, groups=None):
        """Move peds according to forces"""
        # desired velocity
        desired_velocity = self.vel() + self.d_t * force
        desired_velocity = self.capped_velocity(desired_velocity, self.max_speeds)
        # stop when arrived
        # desired_velocity[stateutils.desired_directions(self.state)[1] < 0.5] = [0, 0]

        # update state
        next_state = self.state
        next_state[:, 0:2] += desired_velocity * self.d_t
        next_state[:, 2:4] = desired_velocity
        next_groups = groups if groups is not None else self.groups
        self.update(next_state, next_groups)

    # def desired_directions(self):
    #     return stateutils.desired_directions(self.state)[0]

    @staticmethod
    def capped_velocity(desired_velocity, max_velocity):
        """Scale down a desired velocity to its capped speed."""
        desired_speeds = np.linalg.norm(desired_velocity, axis=-1)
        factor = np.minimum(1.0, max_velocity / desired_speeds)
        factor[desired_speeds == 0] = 0.0
        return desired_velocity * np.expand_dims(factor, -1)

    @property
    def groups(self) -> List[List]:
        return self._groups

    @groups.setter
    def groups(self, groups: List[List]):
        if groups is None:
            self._groups = []
        else:
            self._groups = groups

    def has_group(self):
        return self.groups is not None

    def which_group(self, index: int) -> int:
        """find group index from ped index"""
        for i, group in enumerate(self.groups):
            if index in group:
                return i
        return -1


@dataclass
class EnvState:
    """State of the environment obstacles"""
    _orig_obstacles: List[Line2D]
    _resolution: float = 10
    _obstacles_linspace: List[np.ndarray] = field(init=False)
    _obstacles_raw: np.ndarray = field(init=False)

    def __post_init__(self):
        self._obstacles_raw = self._update_obstacles_raw(self._orig_obstacles)
        self._obstacles_linspace = self._update_obstacles_linspace(self._orig_obstacles)

    @property
    def obstacles_raw(self) -> np.ndarray:
        """a 2D numpy array representing a list of 2D lines
        as (start_x, start_y, end_x, end_y) for array indices 0-3.
        Additionally, the array contains the orthogonal unit vector
        for each 2D line at indices 4-5."""
        return self._obstacles_raw

    @property
    def obstacles(self) -> List[np.ndarray]:
        """a list of np.ndarrays, each representing a uniform
        linspace of 0.1 steps between |p_start, p_end|"""
        return self._obstacles_linspace

    @obstacles.setter
    def obstacles(self, obstacles: List[Line2D]):
        """Input an list of (start_x, end_x, start_y, end_y) as start and end of a line"""
        self._orig_obstacles = obstacles
        self._obstacles_raw = self._update_obstacles_raw(obstacles)
        self._obstacles_linspace = self._update_obstacles_linspace(obstacles)

    def _update_obstacles_linspace(self, obs_lines: List[Line2D]) -> List[np.ndarray]:
        if obs_lines is None:
            obstacles = []
        else:
            obstacles = []
            for start_x, end_x, start_y, end_y in obs_lines:
                samples = int(np.linalg.norm((start_x - end_x, start_y - end_y)) * self._resolution)
                line = np.array(list(zip(
                    np.linspace(start_x, end_x, samples),
                    np.linspace(start_y, end_y, samples))))
                obstacles.append(line)
        return obstacles

    def _update_obstacles_raw(self, obs_lines: List[Line2D]) -> np.ndarray:
        def orient(line):
            start_x, end_x, start_y, end_y = line
            vec_x, vec_y = end_x - start_x, end_y - start_y
            return (atan2(vec_y, vec_x) + 2 * pi) % (2 * pi)

        def unit_vec(orient):
            return cos(orient), sin(orient)

        if obs_lines is None:
            return np.array([])

        line_orients = np.array([orient(line) for line in obs_lines])
        ortho_orients = (line_orients + pi / 2) % (2 * pi)
        ortho_vecs = np.array([unit_vec(orient) for orient in ortho_orients])

        obstacles = np.zeros((len(obs_lines), 6))
        obstacles[:, :4] = [[start_x, start_y, end_x, end_y]
                            for start_x, end_x, start_y, end_y in obs_lines]
        obstacles[:, 4:] = ortho_vecs

        return obstacles
