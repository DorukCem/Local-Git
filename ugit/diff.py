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
   entries = defaultdict(lambda: [None]* len(trees))
   for i, tree in enumerate(trees):
      for path, oid in tree.items():
         entries[path][i] = oid

   for path, oids in entries.items():
      yield (path, *oids)

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