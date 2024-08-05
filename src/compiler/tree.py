from abc import ABC, abstractmethod, ABCMeta
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Generator, Sequence


import pdb

"""
[Current work]
converting all ASTs into dataclasses
- methods operating on the AST nodes will be external, maybe implemented in dewy.py
"""

# TODO: make a nice generic tree maker helper class
# class TreeMaker:
#     """Helper class for generating tree representations of anything"""
#     def __init__(self, draw_branches=True):
#         self.space = '    '
#         if draw_branches:
#             self.branch = '│   '
#             self.tee = '├── '
#             self.last = '└── '
#         else:
#             self.branch = self.space
#             self.tee = self.space
#             self.last = self.space

#         self.level = 0
#         self.prefix = ''

#     def reset(self):
#         self.level = 0
#         self.prefix = ''

#     def indent(self):
#         self.level += 1

#     def dedent(self):
#         if self.level == 0:
#             raise ValueError('Cannot dedent past root level')
#         self.level -= 1

#     def putline(self, line:str) -> str:
