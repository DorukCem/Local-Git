import hashlib
import os
from collections import namedtuple

GIT_DIR = '.ugit'

def init ():
   os.makedirs(GIT_DIR)
   os.makedirs(os.path.join(GIT_DIR, 'objects'))


def hash_object (data, type_='blob'):
   """
    Hashes the given data and stores it in the ugit objects directory.

   Args:
      data: The data to be hashed and stored.
      type_ (str): The type of the object ('blob' for file content, 'tree' for directory content).

   Returns:
      str: The hash (OID) of the stored object.
   """

   #Object have thier type prepended to them as data so we can distinquish between types
   #This allows us to differentiate blob and tree files

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

RefValue = namedtuple("RefValue", ["symbolic", "value"])

def update_ref(ref, value, deref= True):
   """
    Updates the reference with the given value.

    Args:
        ref (str): The name of the reference.
        value (RefValue): The new value of the reference.
        deref (bool): Whether to dereference symbolic references.

    Raises:
        AssertionError: If the value is None or if dereferencing fails.
   """
   ref = _get_ref_internal(ref, deref)[0]

   assert value.value
   if value.symbolic:
      value = f"ref: {value.value}"
   else:
      value = value.value 

   ref_path = os.path.join(GIT_DIR, ref)
   os.makedirs(os.path.dirname(ref_path), exist_ok= True)
   with open(ref_path, 'w') as f:
      f.write(value)

def get_ref(ref, deref= True):
   """
    Retrieves the value of the given reference.

    Args:
        ref (str): The name of the reference.
        deref (bool): Whether to dereference symbolic references.

    Returns:
        RefValue: The value of the reference.
   """
   return _get_ref_internal(ref, deref)[1]

def delete_ref(ref, deref= True):
   ref = _get_ref_internal(ref, deref)[0]
   os.remove(os.path.join(GIT_DIR, ref))

def _get_ref_internal(ref, deref):
   """
      When given a non-symbolic ref, _get_ref_internal will return the ref name and value.
      When given a symbolic ref, _get_ref_internal will dereference the ref recursively, and then return the name of the last (non-symbolic) ref that points to an OID, plus its value.

    Args:
        ref (str): The name of the reference.
        deref (bool): Whether to dereference symbolic references.

    Returns:
        Tuple[str, RefValue]: A tuple containing the reference name and its value.
   """
   ref_path = os.path.join(GIT_DIR, ref)
   value = None
   if os.path.isfile(ref_path):
      with open(ref_path) as f:
         value = f.read().strip()
   
   symbolic = bool(value) and value.startswith("ref:")
   if symbolic:
      value = value.split(":", 1)[1].strip()
      if deref:
         return _get_ref_internal(value, deref=True)
   
   return ref, RefValue(symbolic=symbolic, value=value) 
      
def iter_ref(prefix = '', deref= True):
   """
    Iterates over the references in the repository.

    Args:
        prefix (str): The prefix to filter references.
        deref (bool): Whether to dereference symbolic references.

    Yields:
        Tuple[str, RefValue]: A tuple containing the reference name and its value.
   """
   refs = ['HEAD', 'MERGE_HEAD']
   for root, _ , filenames in os.walk(os.path.join(GIT_DIR, "refs")):
      root = os.path.relpath(root, GIT_DIR)
      refs.extend([os.path.join(root, name) for name in filenames])

   for refname in refs:
      if not refname.startswith(prefix):
         continue
      ref = get_ref(refname, deref=deref)
      if ref.value:
         yield refname, ref