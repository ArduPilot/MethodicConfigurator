PYTHONPATH=../MethodicConfigurator python3 -m coverage run -m unittest annotate_params_test.py
python3 -m coverage html
firefox htmlcov/annotate_params_py.html