"""Run affected lifecycle/house/battle cases, without replaying old import tests.

Regression modules historically execute whole suites on import. Load their
definitions and constants explicitly, then invoke only the named affected
checks. Economy, redeem, purchase and range checks run separately in the builder.
Unchanged research/shop branches retain the prior v75 full-suite evidence.
"""
from pathlib import Path
import sys,ast,importlib.abc,importlib.util,importlib

ROOT=Path(__file__).resolve().parents[1]
class Definitions(importlib.abc.MetaPathFinder,importlib.abc.Loader):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.startswith('check_offline'):
   source=ROOT/'scripts'/f'{fullname}.py'
   if source.exists():return importlib.util.spec_from_loader(fullname,self,origin=str(source))
 def create_module(self,spec):return None
 def exec_module(self,module):
  source=Path(module.__spec__.origin);module.__file__=str(source)
  tree=ast.parse(source.read_text(encoding='utf8'),str(source));nodes=[]
  for node in tree.body:
   if isinstance(node,(ast.Import,ast.ImportFrom,ast.FunctionDef,ast.ClassDef)):nodes.append(node)
   elif isinstance(node,ast.Assign):
    names=[t.id for t in node.targets if isinstance(t,ast.Name)]
    if (names and all(n.isupper() for n in names)) or any(
      isinstance(t,ast.Attribute) and isinstance(t.value,ast.Name) and t.value.id=='core' and t.attr=='OUT'
      for t in node.targets):nodes.append(node)
   elif isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and node.value.func.attr=='insert':nodes.append(node)
  exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),module.__dict__)

if __name__=='__main__':
 sys.meta_path.insert(0,Definitions())
 checks=importlib.import_module('check_offline_pvp_v76_arm')
 checks.check_lifecycle();checks.check_defense();checks.check_residences()
