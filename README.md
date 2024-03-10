# logpool

A easy to use thread pool that provides beautiful customized logging and group task management. 

---
### [Features]

- Manages thread pools optimizing CPU usage.
- Provides logging at multiple levels (inside and out threads): info, warning, critical, and debug.
- Captures and logs exceptions in threads, including a trace.
- Groups tasks for improved management.
- Allows dynamic reconfiguration of logging and thread pool settings.
- Allows shared log across multiple files.

### [Usage]

```python
from log import control ## import the control singleton from the log script.

@control.timer
def some_function(x, y):
    control.info(f"Inside function - {x} and {y} are being added.")
    if x > 100:
        control.warn(f"X is greater than 100: {x}")
    
for i in range(100):
    control.submit(some_function, i**2, i*3, group="sum_func")

control.wait(group="sum_func")
control.info("Finished")

```
