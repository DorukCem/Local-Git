import difflib
from collections import defaultdict
from tempfile import NamedTemporaryFile as Temp
from . import data
import os

def compare_trees(*trees):
   """
    Take a list of trees and return them grouped by filename. 
    This way, for each file we can get all its OIDs in the different trees.
   """
   entries = defaultdict(lambda: [None] * len(trees))
   for i, tree in enumerate(trees):
      for path, oid in tree.items():
         entries[path][i] = oid

   for path, oids in entries.items():
      yield (path, *oids)

def iter_changed_files(t_from, t_to):
   for path, o_from, o_to in compare_trees(t_from, t_to):
      if o_from != o_to:
         action = ("new file" if not o_from else
                   "deleted" if not o_to else
                   "modified")
         yield path, action

def diff_trees(t_from, t_to):
   output = b''
   for path, o_from, o_to in compare_trees(t_from, t_to):
      if o_from != o_to:
         output += diff_blobs(o_from, o_to, path)
   return  output

def diff_blobs(o_from, o_to, path= "blob"):
   # Get the content of the blobs using the provided object IDs
   content_from = data.get_object(o_from, expected="blob")
   content_to = data.get_object(o_to, expected="blob")

   # Split the content into lines for diff comparison
   lines_from = content_from.decode("utf-8").splitlines()
   lines_to = content_to.decode("utf-8").splitlines()

   # Compute the difference between the contents using unified_diff
   diff = difflib.unified_diff(lines_from, lines_to, fromfile=f"a/{path}", tofile=f"b/{path}")

   # Join the diff lines into a single string
   return '\n'.join(diff).encode("utf-8")

def merge_trees(t_HEAD, t_other):
   tree = {}
   for path, o_HEAD, o_other in compare_trees(t_HEAD, t_other):
      tree[path] = merge_blobs(o_HEAD, o_other)
   return tree

def merge_blobs(o_HEAD, o_other):
   data_HEAD = data.get_object(o_HEAD) if o_HEAD else b""
   data_other = data.get_object(o_other) if o_other else b""

   # Decode bytes to strings
   data_HEAD_str = data_HEAD.decode("utf-8")
   data_other_str = data_other.decode("utf-8")

   # Compute the unified diff
   diff = difflib.unified_diff(data_HEAD_str.splitlines(keepends=True), data_other_str.splitlines(keepends=True), 
                               fromfile='HEAD', tofile='other', lineterm='', n= 0)
   
  
   # Join the diff lines into a single string
   return "\n".join(diff).encode("utf-8")