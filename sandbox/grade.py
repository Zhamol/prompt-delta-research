"""Executed ONLY in a separate network-none, read-only grader container."""
import importlib.util
import json
import os
import sys
import unittest
task=sys.argv[1]
sys.path.insert(0,os.environ.get("SUBMISSION_ROOT","/submission")+"/"+task)
spec=importlib.util.spec_from_file_location("independent_grader","/repo/graders/"+task+".py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
print("BENCH_GRADE_JSON "+json.dumps(dict(tests_run=result.testsRun,
    failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
    successful=result.wasSuccessful())),flush=True)
sys.exit(0 if result.wasSuccessful() else 1)
