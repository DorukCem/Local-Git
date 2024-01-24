import os
import itertools
import operator
import string
from collections import namedtuple, deque

from . import data
from . import diff

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

"""
   References:
   References are pointers to specific commits in the repository.
   They can be symbolic or direct:
   Symbolic references are pointers to other references. For example, the HEAD reference is often symbolic, pointing to the current branch or commit.
   Direct references point directly to a commit or object.
   Refs are stored in the .ugit/refs directory as files. Each file represents a reference, with its content being the OID (object ID) of the commit or the reference it points to.

   Branches:
   In this system, branches are a type of reference that points to a specific commit.
   Branches are stored as files within the .ugit/refs/heads directory. Each file represents a branch, and its content is the OID of the commit it points to.
   When you create a new branch, a new file is created in the .ugit/refs/heads directory with the name of the branch, and its content is the OID of the commit it points to.

   When you create a new commit, the branch reference (e.g., refs/heads/master) is updated to point to the new commit.
      In update_ref(), get_ref_internal() returns the ref named branch1 which points to the last commit on that branch
      Then, we change that reference to point to the newest commit in our branch
   
   When you switch branches, the HEAD reference is updated to point to the new branch, and the working directory is updated to match the state of the new branch.

   In some way, branches are just tags that always refer to the last commit of branch: 
   Since head points to a branch when we check it out, any change to the head will also change the branch 
   (such as commits moving the head forward)
   In contrast if we were to checkout the same oid pointed by the branch, the head would point to that oid directly
   and therefore it would not change the branch 
   ( "detached HEAD" state, meaning that HEAD is not pointing to any branch but directly to a commit. 
   In this state, new commits won't update any branch references because HEAD is not associated with a branch.)
   o-----o-----o-----o-----o-----o-----O (3d8773...)
                   \                ^
                    ----o---o    branch1 <--- HEAD
                            ^
                         branch2
"""

def init():
   data.init()
   data.update_ref("HEAD", data.RefValue(symbolic=True, value = os.path.join("refs", "heads", "master")))

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
         result.update(get_tree (oid, os.path.join(path, '')))
      else:
         assert False, f'Unknown tree entry {type_}'
   return result

def get_working_tree():
   result = {}
   for root, _, filenames in os.walk("."):
      for filename in filenames:
         path = os.path.relpath(os.path.join(root, filename))
         if is_ignored(path) or not os.path.isfile(path):
            continue
         with open(path, 'rb') as f:
            result[path] = data.hash_object(f.read())
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

def read_tree_merged(t_HEAD, t_other):
   _empty_current_directory()
   for path, blob in diff.merge_trees(get_tree(t_HEAD), get_tree(t_other)).items():
      os.makedirs(os.path.join(".", os.path.dirname(path)), exist_ok=True)
      with open(path, 'wb') as f:
         f.write(blob)

def commit(message):
   """
    Creates a new commit object representing the current state of the repository.

    Args:
        message (str): The commit message.

    Returns:
        str: The OID of the newly created commit object.
   """

   commit = f"tree {write_tree()}\n"

   # Include the parent commit reference if it exists (for non-initial commits)
   HEAD = data.get_ref('HEAD').value
   if HEAD:
      commit += f"parent {HEAD}\n"

   MERGE_HEAD = data.get_ref('MERGE HEAD').value
   if MERGE_HEAD:
      commit += f"parent {MERGE_HEAD}\n"
      data.delete_ref('MERGE_HEAD', deref= False)

   commit += "\n"
   commit += f"{message}\n"

   oid = data.hash_object(commit.encode(), 'commit')
   # Update the HEAD reference to point to the new commit
   data.update_ref('HEAD', data.RefValue(symbolic=False, value=oid))
   return oid

def checkout(name):
   """
    Updates the working directory to match the state of a specific commit.

    Args:
        name (str): The name of the commit to check out.
   """
   oid = get_oid(name)
   commit = get_commit(oid)
   read_tree(commit.tree)

   if is_branch(name):
      # If it's a branch, update the HEAD reference to point to the branch (last commit on that branch)
      HEAD = data.RefValue(symbolic= True, value= os.path.join("refs", "heads", name))
   else:
      HEAD = data.RefValue(symbolic= False, value= oid)
   data.update_ref("HEAD", HEAD, deref= False)

# TODO reset --hard()
def reset(oid):
   data.update_ref("HEAD", data.RefValue(symbolic=False, value=oid))

def merge(other):
   HEAD = data.get_ref("HEAD").value
   assert HEAD
   c_HEAD = get_commit(HEAD)
   c_other = get_commit(other)

   data.update_ref('MERGE_HEAD', data.RefValue(symbolic=False, value=other))

   read_tree_merged(c_HEAD.tree, c_other.tree)
   print("Merged in working tree\nPlease commit")

def get_merge_base(oid1, oid2):
   """
      Finds the firt common ancestor of two commits
         commit C    commit A
         v           v
      o---o---o---o---o
         \\
          \\ --o---o
                  ^
                  commit B
      (In this example C is the common ancestor of A and B)
   """
   # Saves all parents of the first commit to a set and it iterates over the parents of the 
   # second commit in ancestry order until it reaches a parent that is a parent of the first commit
   parents1 = set(iter_commits_and_parents({oid1}))

   for oid in iter_commits_and_parents({oid2}):
      if oid in parents1:
         return oid

def create_tag(name, oid):
   data.update_ref(os.path.join("refs", "tags", name), data.RefValue(symbolic=False, value=oid))

def create_branch(name, oid):
   data.update_ref(os.path.join("refs", "heads", name), data.RefValue(symbolic=False, value=oid))

def iter_branch_names():
   for refname, _ in data.iter_ref(os.path.join("refs", "heads")):
      yield os.path.relpath(refname, os.path.join("refs", "heads"))

def is_branch(branch):
   return data.get_ref(os.path.join("refs", "heads", branch)).value is not None

def get_branch_name():
   HEAD = data.get_ref("HEAD", deref= False)
   if not HEAD.symbolic:
      return None
   HEAD = HEAD.value
   assert HEAD.startswith(os.path.join("refs", "heads"))
   return os.path.relpath(HEAD, os.path.join("refs", "heads"))

Commit = namedtuple('Commit', ['tree', 'parents', 'message'])

def get_commit(oid):
   """
    Retrieves a commit object from the repository.

    Args:
        oid (str): The OID of the commit object to retrieve.

    Returns:
        Commit: A named tuple representing the commit object with fields for tree OID, parent OID, and message.
   """
   parents = []

   commit = data.get_object(oid, 'commit').decode()
   lines = iter(commit.splitlines())
   for line in itertools.takewhile(operator.truth, lines):
      key, value = line.split(' ', 1)
      if key == 'tree':
         tree = value
      elif key == 'parent':
         parents.append(value)
      else:
         assert False, f"Unknown field {key}"

   message = "\n".join(lines)
   return Commit(tree= tree, parents= parents, message= message)

def iter_commits_and_parents(oids):
   oids = deque(oids)
   visited = set()

   while oids:
      oid = oids.popleft()
      if not oid or oid in visited:
         continue
      visited.add(oid)
      yield oid

      commit = get_commit(oid)

      oids.extendleft(commit.parents[:1])
      oids.extend(commit.parents[1:])

def get_oid(name):
   if name == '@': name = "HEAD"

   refs_to_try = [
      name,
      os.path.join("refs", name),
      os.path.join("refs", "tags", name),
      os.path.join("refs", "heads", name ),
   ]

   for ref in refs_to_try:
      if data.get_ref(ref, deref=False).value:
         return data.get_ref(ref).value
      
   is_hex = all( map(lambda x : x in string.hexdigits, name)) 
   if len(name) == 40 and is_hex:
      return name
   
   assert False, f"Unknown name {name}"
   

def is_ignored(path):
   return '.ugit' in path.split(os.path.sep)