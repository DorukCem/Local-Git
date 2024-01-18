import os
import itertools
import operator
import string
from collections import namedtuple

from . import data

"""
   Our .git/objects folder consits of object files. Object files names are the hashed version of their inner content.
   There a few object types: 1) blob: These objects are regular files which contain data 
   2) tree: These objects  contain metadata about the file sturcture at a given moment. 
   3) commit: These objects represent a snapshot of the project at a specific point in time. They reference a tree object  and can have a parent commit, forming a commit history. They also contain a commit message 

   For example: 
      We have two files in our folder code1 and code2
      Then we run the command git commit
      This creates a tree object with an oid like 123141
      The objet stores the information inside it:
         blob 7182 code1.txt
         blob 48ed code2.txt

      When we run git commit 123141 (the oid we got from our previous commit)
      We can read the contents of Tree Object 123141 and find the blob files of interest
      In this case they are 7182 and 48ed
      We then popualte the current working directory with these files since they 
      were te files that we had at the time of the commit
"""


def write_tree (directory='.'):
   """
    Recursively builds a tree object from the given directory.

    Args:
        directory (str): The path to the directory to build the tree from.

    Returns:
        str: The hash (OID) of the tree object representing the directory structure.
   """
   entries = []
   with os.scandir(directory) as it:
      for entry in it:
         full = os.path.join(directory,entry.name)
         if is_ignored(full):
               continue

         if entry.is_file (follow_symlinks=False):
            type_ = 'blob'
            with open (full, 'rb') as f:
               oid = data.hash_object (f.read ())
         elif entry.is_dir (follow_symlinks=False):
            type_ = 'tree'
            oid = write_tree (full)
         entries.append ((entry.name, oid, type_))

   tree = ''.join(f'{type_} {oid} {name}\n' for name, oid, type_ in sorted (entries))
   return data.hash_object(tree.encode(), 'tree')


def _iter_tree_entries (oid):
   """
    Iterates through the entries of a tree object.
   """
   if not oid:
      return
   tree = data.get_object (oid, 'tree')
   for entry in tree.decode().splitlines():
      type_, oid, name = entry.split(' ', 2)
      yield type_, oid, name


def get_tree (oid, base_path=''):
   """
    Retrieves the tree structure represented by the given tree object OID.

    Args:
        oid (str): The OID of the tree object.
        base_path (str): The base path for the tree structure.

    Returns:
        dict: A dictionary representing the tree structure.
   """
   result = {}
   for type_, oid, name in _iter_tree_entries (oid):
      assert '/' not in name
      assert name not in ('..', '.')
      path = os.path.join(base_path, name)
      if type_ == 'blob':
         result[path] = oid
      elif type_ == 'tree':
         result.update(get_tree (oid, f'{path}/'))
      else:
         assert False, f'Unknown tree entry {type_}'
   return result

def _empty_current_directory ():
   """
    Empties the current directory of all files and subdirectories.
   """
   for root, dirnames, filenames in os.walk ('.', topdown=False):
      for filename in filenames:
         path = os.path.relpath(os.path.join(root,filename))
         if is_ignored (path) or not os.path.isfile (path):
            continue
         os.remove (path)
      for dirname in dirnames:
         path = os.path.relpath(os.path.join(root, dirname))
         if is_ignored (path):
            continue
         try:
            os.rmdir (path)
         except (FileNotFoundError, OSError):
            # Deletion might fail if the directory contains ignored files,
            # so it's OK
            pass

def read_tree (tree_oid):
   """
    Reads a tree object from the repository and recreates the directory structure in the working directory.

    Args:
        tree_oid (str): The OID of the tree object to read.
   """
   _empty_current_directory ()
   for path, oid in get_tree (tree_oid, base_path='./').items():
      os.makedirs (os.path.dirname (path), exist_ok=True)
      with open (path, 'wb') as f:
         f.write (data.get_object (oid))


def commit(message):
   """
    Creates a new commit object representing the current state of the repository.

    Args:
        message (str): The commit message.

    Returns:
        str: The OID of the newly created commit object.
   """

   commit = f"tree {write_tree()}\n"

   HEAD = data.get_ref('HEAD')
   if HEAD:
      commit += f"parent {HEAD}\n"

   commit += "\n"
   commit += f"{message}\n"

   oid = data.hash_object(commit.encode(), 'commit')
   data.update_ref('HEAD', oid)
   return oid

def checkout(oid):
   """
    Updates the working directory to match the state of a specific commit.

    Args:
        oid (str): The OID of the commit to check out.
   """
   commit = get_commit(oid)
   read_tree(commit.tree)
   data.update_ref('HEAD', oid)

def create_tag(name, oid):
   data.update_ref(os.path.join("refs", "tags", name), oid)

Commit = namedtuple('Commit', ['tree', 'parent', 'message'])

def get_commit(oid):
   """
    Retrieves a commit object from the repository.

    Args:
        oid (str): The OID of the commit object to retrieve.

    Returns:
        Commit: A named tuple representing the commit object with fields for tree OID, parent OID, and message.
   """
   parent = None

   commit = data.get_object(oid, 'commit').decode()
   lines = iter(commit.splitlines())
   for line in itertools.takewhile(operator.truth, lines):
      key, value = line.split(' ', 1)
      if key == 'tree':
         tree = value
      elif key == 'parent':
         parent = value
      else:
         assert False, f"Unknown field {key}"

   message = "\n".join(lines)
   return Commit(tree= tree, parent= parent, message= message)

def get_oid(name):
   refs_to_try = [
      name,
      os.path.join("refs", name),
      os.path.join("refs", "tags", name),
      os.path.join("refs", "heads", name ),
   ]

   for ref in refs_to_try:
      if data.get_ref(ref):
         return data.get_ref(ref)
      
   is_hex = all( map(lambda x : x in string.hexdigits, name)) 
   if len(name) == 40 and is_hex:
      return name
   
   assert False, f"Unknown name {name}"
   

def is_ignored(path):
   return '.ugit' in path.split(os.path.sep)