# Imports

TODO

> Syntax likely to change

Examples of imports

```dewy

% import an item from a local file
from p"stuff.dewy" import myfun

% import an item from a local file, and rename it
from p"../some/other/path/to/stuff.dewy" import myfun as myfun2

% import a whole file as an object with a given name.
% tbd if you can omit the name since not an installed library
import p"../../mylib3.dewy" as mylib3

% import all the contents of a file into the current scope
from p"mylib4.dewy" import ...

% import several functions from a local file, unpacking some from nested objects
from p"stuff2.dewy" import myfun2, myfun3 as f1, mymodule as [f2 f3 mod3 as [f4 f5]]

%importing from a whole folder
from p"myproject" import mod1, mod2, mod3

%TODO: what about glob patterns in the import path?
from p"myproject/*.dewy" import ...

% import a whole installed library
import IO

% import items from an installed library
from Math import sin, cos, tan

% import and rename a whole installed library
import seaborn as sns

% import and rename items from an installed library
from sklearn import RandomForest as RF, LinearRegression as LR
```
