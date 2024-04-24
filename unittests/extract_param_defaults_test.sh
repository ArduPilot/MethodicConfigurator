PYTHONPATH=../MethodicConfigurator python3 -m coverage run -m unittest extract_param_defaults_test.py
python3 -m coverage html
firefox htmlcov/extract_param_defaults_py.html