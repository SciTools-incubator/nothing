# [nothing.py](nothing.py)

## An installable Python parent class to support do-nothing workflows.

```shell
python nothing.py --help
```

[Read more about do-nothing workflows](https://blog.danslimmon.com/2019/07/15/do-nothing-scripting-the-key-to-gradual-automation/).

## Features

- Reloadable
  - Stores a progress file (JSON) during execution, which can be loaded to 
    resume from where it left off.
  - The progress file can be human-edited before loading. E.g. skip a step, or
    change a value.
- `get_input()`: a convenience for capturing input with a prompt.
- `wait_for_done()`: a convenience for the user to confirm step completion.
- `report_problem()`: a convenience for printing to `stderr`.
- `set_value_from_input()`: a convenience for setting a value based on user
  input, including offering a default value if available, and repeating the
  prompt until a valid value is entered.

## Use

- Install directly from GitHub.
  - `pip install git+https://github.com/SciTools-incubator/nothing.git`
  - Include in a requirements file:
    - In a `requirements.txt`: `git+https://github.com/SciTools-incubator/nothing.git`
    - In the `pip:` section of a Conda YAML: `- -e git://github.com/SciTools-incubator/nothing.git`
- Create your own subclass of the `Progress` class. See the `Demo` class in
  [nothing.py](nothing.py) for an example.
- Create a script that calls `YourClass.main()`.
