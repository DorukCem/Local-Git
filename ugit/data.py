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
    point a reference to an OID

    Args:
        oid (str): The OID to set as the HEAD reference.
   """
   ref_path = os.path.join(GIT_DIR, ref)
   os.makedirs(os.path.dirname(ref_path), exist_ok= True)
   with open(ref_path, 'w') as f:
      f.write(oid)

def get_ref(ref):
   """
    Returns:
        str: The OID pointed to by the reference.
   """
   ref_path = os.path.join(GIT_DIR, ref)
   if os.path.isfile(ref_path):
      with open(ref_path) as f:
         return f.read().strip()