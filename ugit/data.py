import hashlib
import os

GIT_DIR = '.ugit'

def init ():
   os.makedirs(os.path.join(GIT_DIR, 'objects'))

"""
   Object have thier type prepended to them as data so we can distinquish between types
   This allows us to differentiate blob and tree files
"""
def hash_object (data, type_='blob'):
   """
    Hashes the given data and stores it in the ugit objects directory.

   Args:
      data: The data to be hashed and stored.
      type_ (str): The type of the object ('blob' for file content, 'tree' for directory content).

   Returns:
      str: The hash (OID) of the stored object.
   """
   obj = type_.encode () + b'\x00' + data # Contents are only encoded 
   oid = hashlib.sha1(obj).hexdigest () # Name is hashed
   with open(os.path.join(GIT_DIR, 'objects', oid), 'wb') as out:
      out.write(obj)
   return oid

def get_object (oid, expected='blob'):
   """
    Retrieves the object with the given OID from the ugit objects directory.

    Args:
        oid (str): The OID of the object to retrieve.
        expected (str): The expected type of the object ('blob' or 'tree').

    Returns:
        bytes: The content of the retrieved object.

    Raises:
        AssertionError: If the retrieved object's type does not match the expected type.
   """
   with open(os.path.join(GIT_DIR, 'objects', oid), 'rb') as f:
      obj = f.read ()

   type_, _, content = obj.partition (b'\x00')
   type_ = type_.decode ()

   if expected is not None:
      assert type_ == expected, f'Expected {expected}, got {type_}'
   return content

def update_ref(ref, oid):
   """
    Updates the reference pointed to by `ref` to point to the object with OID `oid`.

    Args:
        ref (str): The reference to be updated (e.g., 'HEAD', 'master').
        oid (str): The OID of the object to which the reference should point.
   """
   ref_path = os.path.join(GIT_DIR, ref)
   os.makedirs(os.path.dirname(ref_path), exist_ok= True)
   with open(ref_path, 'w') as f:
      f.write(oid)

def get_ref(ref):
   """
    Retrieves the OID (object ID) that the reference `ref` points to.

   """

   ref_path = os.path.join(GIT_DIR, ref)
   if os.path.isfile(ref_path):
      with open(ref_path) as f:
         return f.read().strip()
      
def iter_ref():
   refs = ['HEAD']
   for root, _ , filenames in os.walk(os.path.join(GIT_DIR, "refs")):
      root = os.path.relpath(root, GIT_DIR)
      refs.extend([os.path.join(root, name) for name in filenames])

   for refname in refs:
      yield refname, get_ref(refname)