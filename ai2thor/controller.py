# Copyright Allen Institute for Artificial Intelligence 2017
"""
ai2thor.controller

Primary entrypoint into the Thor API. Provides all the high-level functions
needed to control the in-game agent through ai2thor.server.

"""
import atexit
from collections import deque, defaultdict
from itertools import product
import io
import json
import logging
import math
import random
import shlex
import signal
import subprocess
import threading
import os
import platform
try:
    from queue import Queue
except ImportError:
    from Queue import Queue

import zipfile

import numpy as np

import ai2thor.docker
import ai2thor.downloader
import ai2thor.server
from ai2thor.server import queue_get
from ai2thor._builds import BUILDS

logger = logging.getLogger(__name__)


RECEPTACLE_OBJECTS = {
    'Box': {'Candle',
            'CellPhone',
            'Cloth',
            'CreditCard',
            'Dirt',
            'KeyChain',
            'Newspaper',
            'ScrubBrush',
            'SoapBar',
            'SoapBottle',
            'ToiletPaper'},
    'Cabinet': {'Bowl',
                'BowlDirty',
                'Box',
                'Bread',
                'BreadSliced',
                'ButterKnife',
                'Candle',
                'CellPhone',
                'CoffeeMachine',
                'Container',
                'ContainerFull',
                'CreditCard',
                'Cup',
                'Fork',
                'KeyChain',
                'Knife',
                'Laptop',
                'Mug',
                'Newspaper',
                'Pan',
                'Plate',
                'Plunger',
                'Pot',
                'Potato',
                'Sandwich',
                'ScrubBrush',
                'SoapBar',
                'SoapBottle',
                'Spoon',
                'SprayBottle',
                'Statue',
                'TissueBox',
                'Toaster',
                'ToiletPaper',
                'WateringCan'},
    'CoffeeMachine': {'MugFilled', 'Mug'},
    'CounterTop': {'Apple',
                   'AppleSlice',
                   'Bowl',
                   'BowlDirty',
                   'BowlFilled',
                   'Box',
                   'Bread',
                   'BreadSliced',
                   'ButterKnife',
                   'Candle',
                   'CellPhone',
                   'CoffeeMachine',
                   'Container',
                   'ContainerFull',
                   'CreditCard',
                   'Cup',
                   'Egg',
                   'EggFried',
                   'EggShell',
                   'Fork',
                   'HousePlant',
                   'KeyChain',
                   'Knife',
                   'Laptop',
                   'Lettuce',
                   'LettuceSliced',
                   'Microwave',
                   'Mug',
                   'MugFilled',
                   'Newspaper',
                   'Omelette',
                   'Pan',
                   'Plate',
                   'Plunger',
                   'Pot',
                   'Potato',
                   'PotatoSliced',
                   'RemoteControl',
                   'Sandwich',
                   'ScrubBrush',
                   'SoapBar',
                   'SoapBottle',
                   'Spoon',
                   'SprayBottle',
                   'Statue',
                   'Television',
                   'TissueBox',
                   'Toaster',
                   'ToiletPaper',
                   'Tomato',
                   'TomatoSliced',
                   'WateringCan'},
    'Fridge': {'Apple',
               'AppleSlice',
               'Bowl',
               'BowlDirty',
               'BowlFilled',
               'Bread',
               'BreadSliced',
               'Container',
               'ContainerFull',
               'Cup',
               'Egg',
               'EggFried',
               'EggShell',
               'Lettuce',
               'LettuceSliced',
               'Mug',
               'MugFilled',
               'Omelette',
               'Pan',
               'Plate',
               'Pot',
               'Potato',
               'PotatoSliced',
               'Sandwich',
               'Tomato',
               'TomatoSliced'},
    'GarbageCan': {'Apple',
                   'AppleSlice',
                   'Box',
                   'Bread',
                   'BreadSliced',
                   'Candle',
                   'CellPhone',
                   'CreditCard',
                   'Egg',
                   'EggFried',
                   'EggShell',
                   'LettuceSliced',
                   'Newspaper',
                   'Omelette',
                   'Plunger',
                   'Potato',
                   'PotatoSliced',
                   'Sandwich',
                   'ScrubBrush',
                   'SoapBar',
                   'SoapBottle',
                   'SprayBottle',
                   'Statue',
                   'ToiletPaper',
                   'Tomato',
                   'TomatoSliced'},
    'Microwave': {'Bowl',
                  'BowlDirty',
                  'BowlFilled',
                  'Bread',
                  'BreadSliced',
                  'Container',
                  'ContainerFull',
                  'Cup',
                  'Egg',
                  'EggFried',
                  'Mug',
                  'MugFilled',
                  'Omelette',
                  'Plate',
                  'Potato',
                  'PotatoSliced',
                  'Sandwich'},
    'PaintingHanger': {'Painting'},
    'Pan': {'Apple',
            'AppleSlice',
            'EggFried',
            'Lettuce',
            'LettuceSliced',
            'Omelette',
            'Potato',
            'PotatoSliced',
            'Tomato',
            'TomatoSliced'},
    'Pot': {'Apple',
            'AppleSlice',
            'EggFried',
            'Lettuce',
            'LettuceSliced',
            'Omelette',
            'Potato',
            'PotatoSliced',
            'Tomato',
            'TomatoSliced'},
    'Sink': {'Apple',
             'AppleSlice',
             'Bowl',
             'BowlDirty',
             'BowlFilled',
             'ButterKnife',
             'Container',
             'ContainerFull',
             'Cup',
             'Egg',
             'EggFried',
             'EggShell',
             'Fork',
             'Knife',
             'Lettuce',
             'LettuceSliced',
             'Mug',
             'MugFilled',
             'Omelette',
             'Pan',
             'Plate',
             'Pot',
             'Potato',
             'PotatoSliced',
             'Sandwich',
             'ScrubBrush',
             'SoapBottle',
             'Spoon',
             'Tomato',
             'TomatoSliced',
             'WateringCan'},
    'StoveBurner': {'Omelette', 'Pot', 'Pan', 'EggFried'},
    'TableTop': {'Apple',
                 'AppleSlice',
                 'Bowl',
                 'BowlDirty',
                 'BowlFilled',
                 'Box',
                 'Bread',
                 'BreadSliced',
                 'ButterKnife',
                 'Candle',
                 'CellPhone',
                 'CoffeeMachine',
                 'Container',
                 'ContainerFull',
                 'CreditCard',
                 'Cup',
                 'Egg',
                 'EggFried',
                 'EggShell',
                 'Fork',
                 'HousePlant',
                 'KeyChain',
                 'Knife',
                 'Laptop',
                 'Lettuce',
                 'LettuceSliced',
                 'Microwave',
                 'Mug',
                 'MugFilled',
                 'Newspaper',
                 'Omelette',
                 'Pan',
                 'Plate',
                 'Plunger',
                 'Pot',
                 'Potato',
                 'PotatoSliced',
                 'RemoteControl',
                 'Sandwich',
                 'ScrubBrush',
                 'SoapBar',
                 'SoapBottle',
                 'Spoon',
                 'SprayBottle',
                 'Statue',
                 'Television',
                 'TissueBox',
                 'Toaster',
                 'ToiletPaper',
                 'Tomato',
                 'TomatoSliced',
                 'WateringCan'},
    'ToiletPaperHanger': {'ToiletPaper'},
    'TowelHolder': {'Cloth'}}



def process_alive(pid):
    """
    Use kill(0) to determine if pid is alive
    :param pid: process id
    :rtype: bool
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False

    return True

# python2.7 compatible makedirs
def makedirs(directory):
    if not os.path.isdir(directory):
        os.makedirs(directory)

def distance(point1, point2):
    x_diff = (point1['x'] - point2['x']) ** 2
    z_diff = (point1['z'] - point2['z']) ** 2
    return math.sqrt(x_diff + z_diff)


def key_for_point(x, z):
    return "%0.1f %0.1f" % (x, z)

class Controller(object):

    def __init__(self):
        self.request_queue = Queue(maxsize=1)
        self.response_queue = Queue(maxsize=1)
        self.receptacle_nearest_pivot_points = {}
        self.server = None
        self.unity_pid = None
        self.docker_enabled = False
        self.container_id = None
        self.local_executable_path = None
        self.last_event = None
        self.server_thread = None

    def reset(self, scene_name=None):
        self.response_queue.put_nowait(dict(action='Reset', sceneName=scene_name, sequenceId=0))
        self.last_event = queue_get(self.request_queue)

        return self.last_event

    def random_initialize(
            self,
            random_seed=None,
            randomize_open=False,
            unique_object_types=False,
            exclude_receptacle_object_pairs=[]):

        receptacle_objects = []

        for rec_obj_type, object_types in RECEPTACLE_OBJECTS.items():
            receptacle_objects.append(
                dict(receptacleObjectType=rec_obj_type, itemObjectTypes=list(object_types))
            )
        if random_seed is None:
            random_seed = random.randint(0, 2**32)

        exclude_object_ids = []

        for obj in self.last_event.metadata['objects']:
            pivot_points = self.receptacle_nearest_pivot_points
            # don't put things in pot or pan currently
            if (pivot_points and obj['receptacle'] \
                and pivot_points[obj['objectId']].keys()) \
                or obj['objectType'] in ['Pot', 'Pan']:

                #print("no visible pivots for receptacle %s" % o['objectId'])
                exclude_object_ids.append(obj['objectId'])

        return self.step(dict(
            action='RandomInitialize',
            receptacleObjects=receptacle_objects,
            randomizeOpen=randomize_open,
            uniquePickupableObjectTypes=unique_object_types,
            excludeObjectIds=exclude_object_ids,
            excludeReceptacleObjectPairs=exclude_receptacle_object_pairs,
            randomSeed=random_seed))

    def step(self, action, raise_for_failure=False):
        if not self._check_action(action):
            new_event = ai2thor.server.Event(
                json.loads(json.dumps(self.last_event.metadata)),
                self.last_event.image)

            new_event.metadata['lastActionSuccess'] = False
            self.last_event = new_event
            return new_event
        assert self.request_queue.empty()

        # Converts numpy scalars to python scalars so they can be encoded in
        # JSON.
        action_filtered = {}
        for k,v in action.items():
            if isinstance(v, np.generic):
                v = np.asscalar(v)
            action_filtered[k] = v
        action = action_filtered

        self.response_queue.put_nowait(action)
        self.last_event = queue_get(self.request_queue)
        #print(self.last_event.metadata['errorMessage'])
        if raise_for_failure:
            assert self.last_event.metadata['lastActionSuccess']

        return self.last_event

    def unity_command(self, width, height):

        command = self.executable_path()
        command += " -screen-width %s -screen-height %s" % (width, height)
        return shlex.split(command)

    def _start_thread(self, env, width, height, host, port, image_name, start_unity):
        # get environment variables

        if not start_unity:
            self.server.client_token = None

        _, port = self.server.wsgi_server.socket.getsockname()


        env['AI2THOR_VERSION'] = ai2thor._builds.VERSION
        env['AI2THOR_HOST'] = host
        env['AI2THOR_PORT'] = str(port)
        env['AI2THOR_CLIENT_TOKEN'] = self.server.client_token
        env['AI2THOR_SCREEN_WIDTH'] = str(width)
        env['AI2THOR_SCREEN_HEIGHT'] = str(height)


        # env['AI2THOR_SERVER_SIDE_SCREENSHOT'] = 'True'

        # print("Viewer: http://%s:%s/viewer" % (host, port))

        # launch simulator
        if start_unity:

            if image_name is not None:
                self.container_id = ai2thor.docker.run(image_name, env)
                atexit.register(lambda: ai2thor.docker.kill_container(self.container_id))
            else:
                proc = subprocess.Popen(self.unity_command(width, height), env=env)
                self.unity_pid = proc.pid

                # print("launched pid %s" % self.unity_pid)
                atexit.register(lambda: os.kill(self.unity_pid, signal.SIGKILL))

        self.server.start()

    def base_dir(self):
        return os.path.join(os.path.expanduser('~'), '.ai2thor')

    def build_name(self):
        return os.path.splitext(os.path.basename(BUILDS[platform.system()]['url']))[0]

    def executable_path(self):

        if self.local_executable_path is not None:
            return self.local_executable_path

        target_arch = platform.system()

        if target_arch == 'Linux':
            return os.path.join(self.base_dir(), 'releases', self.build_name(), self.build_name())
        elif target_arch == 'Darwin':
            return os.path.join(
                self.base_dir(),
                'releases',
                self.build_name(),
                self.build_name() + ".app",
                "Contents/MacOS",
                self.build_name())
        else:
            raise Exception('unable to handle target arch %s' % target_arch)

    def download_binary(self):

        if platform.architecture()[0] != '64bit':
            raise Exception("Only 64bit currently supported")

        url = BUILDS[platform.system()]['url']
        releases_dir = os.path.join(self.base_dir(), 'releases')
        tmp_dir = os.path.join(self.base_dir(), 'tmp')
        makedirs(releases_dir)
        makedirs(tmp_dir)

        if not os.path.isfile(self.executable_path()):
            zip_data = ai2thor.downloader.download(
                url,
                self.build_name(),
                BUILDS[platform.system()]['sha256'])

            z = zipfile.ZipFile(io.BytesIO(zip_data))
            # use tmpdir instead or a random number
            extract_dir = os.path.join(tmp_dir, self.build_name())
            logger.debug("Extracting zipfile %s" % os.path.basename(url))
            z.extractall(extract_dir)
            os.rename(extract_dir, os.path.join(releases_dir, self.build_name()))
            # we can lose the executable permission when unzipping a build
            os.chmod(self.executable_path(), 0o755)
        else:
            logger.debug("%s exists - skipping download" % self.executable_path())
    


    def start(
            self,
            port=0,
            start_unity=True,
            player_screen_width=300,
            player_screen_height=300,
            x_display="0.0"):

        if player_screen_height < 300 or player_screen_width < 300:
            raise Exception("Screen resolution must be >= 300x300")

        if self.server_thread is not None:
            raise Exception("server has already been started - cannot start more than once")

        env = os.environ.copy()

        image_name = None
        host = '127.0.0.1'

        if start_unity:
            if platform.system() == 'Linux':

                if self.docker_enabled and ai2thor.docker.has_docker() and ai2thor.docker.nvidia_version() is not None:
                    image_name = ai2thor.docker.build_image()
                    host = ai2thor.docker.bridge_gateway()
                else:
                    env['DISPLAY'] = ':' + x_display
                    self.download_binary()
            else:
                self.download_binary()

        self.server = ai2thor.server.Server(
            self.request_queue,
            self.response_queue,
            host,
            port=port)

        self.server_thread = threading.Thread(
            target=self._start_thread,
            args=(env, player_screen_width, player_screen_height, host, port, image_name, start_unity))
        self.server_thread.daemon = True
        self.server_thread.start()

        # receive the first request
        self.last_event = queue_get(self.request_queue)

        return self.last_event

    def stop(self):
        self.stop_unity()
        self.stop_container()
        self.server.wsgi_server.shutdown()

    def stop_container(self):
        if self.container_id:
            ai2thor.docker.kill_container(self.container_id)
            self.container_id = None

    def stop_unity(self):
        if self.unity_pid and process_alive(self.unity_pid):
            os.kill(self.unity_pid, signal.SIGKILL)

    def _check_action(self, _):
        return True

class BFSSearchPoint:
    def __init__(self, start_position, move_vector, heading_angle=0.0, horizon_angle=0.0):
        self.start_position = start_position
        self.move_vector = defaultdict(lambda: 0.0)
        self.move_vector.update(move_vector)
        self.heading_angle = heading_angle
        self.horizon_angle = horizon_angle

    def target_point(self):
        x = self.start_position['x'] + self.move_vector['x']
        z = self.start_position['z'] + self.move_vector['z']
        return dict(x=x, z=z)

class BFSController(Controller):

    def __init__(self):
        super(BFSController, self).__init__()
        self.rotations = [0, 90, 180, 270]
        self.horizons = [330, 0, 30]
        self.allow_enqueue = True
        self.queue = deque()
        self.seen_points = []
        self.grid_points = []
        self.grid_size = 0.25

    def visualize_points(self, scene_name, wait_key=10):
        import cv2
        points = set()
        xs = []
        zs = []

            # Follow the file as it grows
        for point in self.grid_points:
            xs.append(point['x'])
            zs.append(point['z'])
            points.add(str(point['x']) + "," + str(point['z']))

        image_width = 470
        image_height = 530
        image = np.zeros((image_height, image_width, 3), np.uint8)
        if not xs:
            return

        min_x = min(xs)  - 1
        max_x = max(xs) + 1
        min_z = min(zs)  - 1
        max_z = max(zs) + 1

        for point in list(points):
            x, z = map(float, point.split(','))
            circle_x = round(((x - min_x)/float(max_x - min_x)) * image_width)
            z = (max_z - z) + min_z
            circle_y = round(((z - min_z)/float(max_z - min_z)) * image_height)
            cv2.circle(image, (circle_x, circle_y), 5, (0, 255, 0), -1)

        cv2.imshow(scene_name, image)
        cv2.waitKey(wait_key)


    def has_islands(self):
        queue = []
        seen_points = set()
        mag = self.grid_size
        def enqueue_island_points(p):
            if json.dumps(p) in seen_points:
                return
            queue.append(dict(z=p['z'] + mag, x=p['x']))
            queue.append(dict(z=p['z'] - mag, x=p['x']))
            queue.append(dict(z=p['z'], x=p['x'] + mag))
            queue.append(dict(z=p['z'], x=p['x'] - mag))
            seen_points.add(json.dumps(p))


        enqueue_island_points(self.grid_points[0])

        while queue:
            point_to_find = queue.pop()
            for p in self.grid_points:
                dist = math.sqrt(
                    ((point_to_find['x'] - p['x']) ** 2) + \
                    ((point_to_find['z'] - p['z']) ** 2))

                if dist < 0.05:
                    enqueue_island_points(p)

        return len(seen_points) != len(self.grid_points)

    def build_graph(self):
        import networkx as nx
        graph = nx.Graph()
        for point in self.grid_points:
            self._build_graph_point(graph, point)

        return graph

    def key_for_point(self, point):
        return "{x:0.3f}|{z:0.3f}".format(**point)

    def _build_graph_point(self, graph, point):
        for p in self.grid_points:
            dist = math.sqrt(((point['x'] - p['x']) ** 2) + ((point['z'] - p['z']) ** 2))
            if dist <= (self.grid_size + 0.01) and dist > 0:
                graph.add_edge(self.key_for_point(point), self.key_for_point(p))

    def move_relative_points(self, all_points, graph, position, rotation):

        action_orientation = {
            0:dict(x=0, z=1, action='MoveAhead'),
            90:dict(x=1, z=0, action='MoveRight'),
            180:dict(x=0, z=-1, action='MoveBack'),
            270:dict(x=-1, z=0, action='MoveLeft')
        }

        move_points = dict()

        for n in graph.neighbors(self.key_for_point(position)):
            point = all_points[n]
            x_o = round((point['x'] - position['x']) / self.grid_size)
            z_o = round((point['z'] - position['z']) / self.grid_size)
            for target_rotation, offsets in action_orientation.items():
                delta = round(rotation + target_rotation) % 360
                ao = action_orientation[delta]
                action_name = action_orientation[target_rotation]['action']
                if x_o == ao['x'] and z_o == ao['z']:
                    move_points[action_name] = point
                    break

        return move_points

    def plan_horizons(self, agent_horizon, target_horizon):
        actions = []
        horizon_step_map = {330:3, 0:2, 30:1, 60:0}
        look_diff = horizon_step_map[int(agent_horizon)] - horizon_step_map[int(target_horizon)]
        if look_diff > 0:
            for i in range(look_diff):
                actions.append(dict(action='LookDown'))
        else:
            for i in range(abs(look_diff)):
                actions.append(dict(action='LookUp'))

        return actions

    def plan_rotations(self, agent_rotation, target_rotation):
        right_diff = target_rotation - agent_rotation
        if right_diff < 0:
            right_diff += 360
        right_steps = right_diff / 90

        left_diff = agent_rotation - target_rotation
        if left_diff < 0:
            left_diff += 360
        left_steps = left_diff / 90

        actions = []
        if right_steps < left_steps:
            for i in range(int(right_steps)):
                actions.append(dict(action='RotateRight'))
        else:
            for i in range(int(left_steps)):
                actions.append(dict(action='RotateLeft'))

        return actions

    def shortest_plan(self, graph, agent, target):
        import networkx as nx
        path = nx.shortest_path(graph, self.key_for_point(agent['position']), self.key_for_point(target['position']))
        actions = []
        all_points = {}

        for point in self.grid_points:
            all_points[self.key_for_point(point)] = point

        #assert all_points[path[0]] == agent['position']

        current_position = agent['position']
        current_rotation = agent['rotation']['y']

        for p in path[1:]:
            inv_pms = {self.key_for_point(v): k for k, v in self.move_relative_points(all_points, graph, current_position, current_rotation).items()}
            actions.append(dict(action=inv_pms[p]))
            current_position = all_points[p]

        actions += self.plan_horizons(agent['cameraHorizon'], target['cameraHorizon'])
        actions += self.plan_rotations(agent['rotation']['y'], target['rotation']['y'])
        # self.visualize_points(path)

        return actions

    def enqueue_point(self, point):

        # ensure there are no points near the new point
        threshold = self.grid_size/5.0
        if not any(map(lambda p: distance(p, point.target_point()) < threshold, self.seen_points)):
            self.seen_points.append(point.target_point())
            self.queue.append(point)

    def enqueue_points(self, agent_position):
        if not self.allow_enqueue:
            return
        self.enqueue_point(BFSSearchPoint(agent_position, dict(x=-1 * self.grid_size)))
        self.enqueue_point(BFSSearchPoint(agent_position, dict(x=self.grid_size)))
        self.enqueue_point(BFSSearchPoint(agent_position, dict(z=-1 * self.grid_size)))
        self.enqueue_point(BFSSearchPoint(agent_position, dict(z=1 * self.grid_size)))

    def search_all_closed(self, scene_name):
        self.allow_enqueue = True
        self.queue = deque()
        self.seen_points = []
        self.grid_points = []
        event = self.reset(scene_name)
        event = self.step(dict(action='Initialize', gridSize=0.25))
        self.enqueue_points(event.metadata['agent']['position'])
        while self.queue:
            self.queue_step()
            #self.visualize_points(scene_name)

    def start_search(
            self,
            scene_name,
            random_seed,
            full_grid,
            current_receptacle_object_pairs,
            randomize=True):

        self.seen_points = []
        self.queue = deque()
        self.grid_points = []

        # we only search a pre-defined grid with all the cabinets/fridges closed
        # then keep the points that can still be reached
        self.allow_enqueue = True

        for gp in full_grid:
            self.enqueue_points(gp)

        self.allow_enqueue = False

        self.reset(scene_name)
        receptacle_object_pairs = []
        for op in current_receptacle_object_pairs:
            object_id, receptacle_object_id = op.split('||')
            receptacle_object_pairs.append(
                dict(receptacleObjectId=receptacle_object_id,
                     objectId=object_id))


        if randomize:
            self.random_initialize(
                random_seed=random_seed,
                unique_object_types=True,
                exclude_receptacle_object_pairs=receptacle_object_pairs)

        self.initialize_scene()
        while self.queue:
            self.queue_step()
            #self.visualize_points(scene_name)

        self.prune_points()
        #self.visualize_points(scene_name)

    # get rid of unreachable points
    def prune_points(self):
        final_grid_points = set()

        for gp in self.grid_points:
            final_grid_points.add(key_for_point(gp['x'], gp['z']))

        pruned_grid_points = []

        for gp in self.grid_points:
            found = False
            for x in [1, -1]:
                found |= key_for_point(gp['x'] +\
                    (self.grid_size * x), gp['z']) in final_grid_points

            for z in [1, -1]:
                found |= key_for_point(
                    gp['x'],
                    (self.grid_size * z) + gp['z']) in final_grid_points

            if found:
                pruned_grid_points.append(gp)

        self.grid_points = pruned_grid_points

    def is_object_visible(self, object_id):
        for obj in self.last_event.metadata['objects']:
            if obj['objectId'] == object_id and obj['visible']:
                return True
        return False

    def find_visible_receptacles(self):
        receptacle_points = []
        receptacle_pivot_points = []

        # pickup all objects
        visibility_object_id = None
        visibility_object_types = ['Mug', 'CellPhone']
        for obj in self.last_event.metadata['objects']:
            if obj['pickupable']:
                self.step(action=dict(
                    action='PickupObject',
                    objectId=obj['objectId'],
                    forceVisible=True))
            if visibility_object_id is None and obj['objectType'] in visibility_object_types:
                visibility_object_id = obj['objectId']

        for point in self.grid_points:
            self.step(dict(
                action='Teleport',
                x=point['x'],
                y=point['y'],
                z=point['z']), raise_for_failure=True)

            for rot, hor in product(self.rotations, self.horizons):
                event = self.step(
                    dict(action='RotateLook', rotation=rot, horizon=hor),
                    raise_for_failure=True)
                for j in event.metadata['objects']:
                    if j['receptacle'] and j['visible']:
                        receptacle_points.append(dict(
                            distance=j['distance'],
                            pivotId=0,
                            receptacleObjectId=j['objectId'],
                            searchNode=dict(
                                horizon=hor,
                                rotation=rot,
                                openReceptacle=False,
                                pivotId=0,
                                receptacleObjectId='',
                                x=point['x'],
                                y=point['y'],
                                z=point['z'])))

                        if j['openable']:
                            self.step(action=dict(
                                action='OpenObject',
                                forceVisible=True,
                                objectId=j['objectId']),
                                      raise_for_failure=True)
                        for pivot_id in range(j['receptacleCount']):
                            self.step(
                                action=dict(
                                    action='Replace',
                                    forceVisible=True,
                                    receptacleObjectId=j['objectId'],
                                    objectId=visibility_object_id,
                                    pivot=pivot_id, raise_for_failure=True))
                            if self.is_object_visible(visibility_object_id):
                                receptacle_pivot_points.append(dict(
                                    distance=j['distance'],
                                    pivotId=pivot_id,
                                    receptacleObjectId=j['objectId'],
                                    searchNode=dict(
                                        horizon=hor,
                                        rotation=rot,
                                        openReceptacle=j['openable'],
                                        pivotId=pivot_id,
                                        receptacleObjectId=j['objectId'],
                                        x=point['x'],
                                        y=point['y'],
                                        z=point['z'])))


                        if j['openable']:
                            self.step(action=dict(
                                action='CloseObject',
                                forceVisible=True,
                                objectId=j['objectId']),
                                      raise_for_failure=True)

        return receptacle_pivot_points, receptacle_points

    def find_visible_objects(self):

        seen_target_objects = defaultdict(list)

        for point in self.grid_points:
            self.step(dict(
                action='Teleport',
                x=point['x'],
                y=point['y'],
                z=point['z']), raise_for_failure=True)

            for rot, hor in product(self.rotations, self.horizons):
                event = self.step(dict(
                    action='RotateLook',
                    rotation=rot,
                    horizon=hor), raise_for_failure=True)

                object_receptacle = dict()
                for obj in event.metadata['objects']:
                    if obj['receptacle']:
                        for pso in obj['pivotSimObjs']:
                            object_receptacle[pso['objectId']] = obj

                for obj in filter(
                        lambda x: x['visible'] and x['pickupable'],
                        event.metadata['objects']):

                    if obj['objectId'] in object_receptacle and\
                            object_receptacle[obj['objectId']]['openable'] and not \
                            object_receptacle[obj['objectId']]['isopen']:
                        continue

                    seen_target_objects[obj['objectId']].append(dict(
                        distance=obj['distance'],
                        agent=event.metadata['agent']))

        return seen_target_objects

    def initialize_scene(self):
        self.target_objects = []
        self.object_receptacle = defaultdict(
            lambda: dict(objectId='StartupPosition', pivotSimObjs=[]))

        self.open_receptacles = []
        open_pickupable = {}
        pickupable = {}
        for obj in filter(lambda x: x['receptacle'], self.last_event.metadata['objects']):
            for oid in obj['receptacleObjectIds']:
                self.object_receptacle[oid] = obj

        for obj in filter(lambda x: x['receptacle'], self.last_event.metadata['objects']):
            for oid in obj['receptacleObjectIds']:
                if obj['openable'] or (obj['objectId'] in self.object_receptacle \
                    and self.object_receptacle[obj['objectId']]['openable']):

                    open_pickupable[oid] = obj['objectId']
                else:
                    pickupable[oid] = obj['objectId']

        if open_pickupable.keys():
            self.target_objects = random.sample(open_pickupable.keys(), k=1)
            shuffled_keys = list(open_pickupable.keys())
            random.shuffle(shuffled_keys)
            for oid in shuffled_keys:
                position_target = self.object_receptacle[self.target_objects[0]]['position']
                position_candidate = self.object_receptacle[oid]['position']
                dist = math.sqrt(
                    (position_target['x'] - position_candidate['x']) ** 2 + \
                    (position_target['y'] - position_candidate['y']) ** 2)
                # try to find something that is far to avoid having the doors collide
                if dist > 1.25:
                    self.target_objects.append(oid)
                    break

        for roid in set(map(lambda x: open_pickupable[x], self.target_objects)):
            self.open_receptacles.append(roid)
            self.step(dict(
                action='OpenObject',
                objectId=roid,
                forceVisible=True), raise_for_failure=True)

    def queue_step(self):
        search_point = self.queue.popleft()
        event = self.step(dict(
            action='Teleport',
            x=search_point.start_position['x'],
            y=search_point.start_position['y'],
            z=search_point.start_position['z']))

        #print(event.metadata['errorMessage'])
        assert event.metadata['lastActionSuccess']
        move_vec = search_point.move_vector
        move_vec['moveMagnitude'] = self.grid_size
        event = self.step(dict(action='Move', **move_vec))

        if event.metadata['lastActionSuccess']:
            if event.metadata['agent']['position']['y'] > 1.3:
                #pprint(search_point.start_position)
                #pprint(search_point.move_vector)
                #pprint(event.metadata['agent']['position'])
                raise Exception("**** got big point ")

            self.enqueue_points(event.metadata['agent']['position'])
            self.grid_points.append(event.metadata['agent']['position'])


        return event
