import hashlib
import os

GIT_DIR = '.ugit'

def init ():
   os.makedirs(os.path.join(GIT_DIR, 'objects'))
   
def hash_object (data, type_='blob'):
   obj = type_.encode () + b'\x00' + data
   oid = hashlib.sha1(obj).hexdigest ()
   with open(os.path.join(GIT_DIR, 'objects', oid), 'wb') as out:
      out.write(obj)
   return oid

def get_object (oid, expected='blob'):
   with open(os.path.join(GIT_DIR, 'objects', oid), 'rb') as f:
      obj = f.read ()

   type_, _, content = obj.partition (b'\x00')
   type_ = type_.decode ()

   if expected is not None:
      assert type_ == expected, f'Expected {expected}, got {type_}'
   return content

def set_HEAD(oid):
   with open(os.path.join(GIT_DIR, 'HEAD'), "w") as f:
      f.write(oid)

def get_HEAD():
   head_file = os.path.join(GIT_DIR, 'HEAD')
   if os.path.isfile(head_file):
      with open(head_file) as f:
         return f.read().strip()