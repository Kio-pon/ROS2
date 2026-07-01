import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'drone_controller'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='azyan',
    maintainer_email='azyan@todo.todo',
    description='My first ROS 2 drone controller package',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'offboard_control = drone_controller.offboard_position_control:main',
            'autonomous_mission = drone_controller.autonomous_mission:main',
            'drone_visualizer = drone_controller.drone_visualizer:main',
            'drone_keyboard_teleop = drone_controller.drone_keyboard_teleop:main',
            'mission_control = drone_controller.mission_control:main',
            'camera_proof = drone_controller.camera_proof:main',
            'm4e_controller = drone_controller.m4e_controller:main',
            'camera_switcher = drone_controller.camera_switcher:main',
        ],
    },
)
