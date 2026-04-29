from setuptools import setup
from glob import glob

package_name = 'digital_twin'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name, package_name + '.nodes'],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/worlds',
            glob('digital_twin/worlds/*.wbt')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='root',
    maintainer_email='root@todo.todo',
    description='Industrial Digital Twin',
    license='MIT',
    entry_points={
        'console_scripts': [
            'plc_simulator = digital_twin.nodes.plc_simulator_node:main',
            'webots_bridge = digital_twin.nodes.webots_bridge_node:main',
            'cv_node = digital_twin.nodes.cv_node:main',
            'fault_detection = digital_twin.nodes.fault_detection_node:main',
        ],
    },
)
