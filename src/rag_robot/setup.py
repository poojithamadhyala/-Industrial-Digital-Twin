from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'rag_robot'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch',
            glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Your Name',
    maintainer_email='you@example.com',
    description='RAG-powered voice-controlled robot bridge',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'rag_bridge_node = rag_robot.rag_bridge_node:main',
            'tts_node = rag_robot.tts_node:main',
        ],
    },
)
