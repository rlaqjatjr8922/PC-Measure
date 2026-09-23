"""Import cached shared services; feature files remain tiny run() entrypoints."""
import importlib.util
import inspect
from core import runtime as rt


def execute(group, feature, arguments, record=True):
    path = rt.BASE / group / (feature+'.py')
    if not path.resolve().is_relative_to(rt.BASE.resolve()):
        rt.fail('잘못된 기능 경로입니다.')
    spec = importlib.util.spec_from_file_location('pc_control_'+group+'_'+feature, path)
    if spec is None or spec.loader is None or not path.is_file():
        rt.fail('기능 파일이 없습니다.',404)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run(**arguments)
    if inspect.isawaitable(result):
        rt.fail('동기 기능에서 비동기 결과를 반환했습니다.',500)
    if record:
        from core.macros import automation
        automation(group, feature, arguments)
    return result
