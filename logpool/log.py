from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import threading
import inspect
import os
from datetime import datetime
import time
import psutil
from threading import Lock

class ControlThreads:
    """
    A thread and process pool executor that provides enhanced logging capabilities,
    group task management, and customized logging functionalities.
    
    Methods
    -------
    submit(fn, *args, group="default", **kwargs):
        Submit a function to be executed by the thread or process pool, optionally assigning it to a group.
    get_logs():
        Returns the content of the log file as a list of strings.
    get_queue(group='default'):
        Returns a list indicating the completion status of tasks in a specified group.
    info(content, **kwargs), time(content), warn(content), critical(content), debug(content):
        Methods to log messages of different severities.
    clear_logs():
        Clears the log file.
    finishLog(filename):
        Copies the current log file to a new location and clears the log.

    Examples
    --------
    >>> from log import control
    >>> control.reconfigured() # If you want to change something
    >>> def task(x):
    ...     control.info("Written from thread.") 
    ...     return x*x
    >>> future = control.submit(task, 2)
    >>> control.info("Task submitted.")
    >>> control.wait()
    >>> print(future.result())
    """
    
    def __init__(
        self, 
        log_file=None, 
        print_log=True, 
        debug=False, 
        max_workers=psutil.cpu_count(logical=True) - 2, 
        use_process_pool=False,
        keep_in_memory=False
    ):
        
        """
        Initialize the ControlThreads object.

        Args:
            log_file (str): Path to the log file. If None, logging to a file is disabled.
            print_log (bool): Whether to print log messages to the console.
            debug (bool): Whether to enable debug mode.
            max_workers (int): Maximum number of worker threads or processes to use.
            use_process_pool (bool): Whether to use a process pool instead of a thread pool.
        """
        self.lock = Lock()
        self.tasks = {'default': []}
        self.log_file = log_file
        if self.log_file is not None:
            self._init_log()
        self.workers = max_workers
        self.print_log = print_log
        self.debug_mode = debug
        self.use_process_pool = use_process_pool
        
        self.keep_in_memory = keep_in_memory
        self.memory = []
        
        self.executor = ProcessPoolExecutor(max_workers) if use_process_pool else ThreadPoolExecutor(max_workers)
    
    def reconfigure(self, *args, **kwargs):
        """
        Reconfigure the ControlThreads object with new settings.

        Args:
            log_file (str): Path to the log file. If None, logging to a file is disabled.
            print_log (bool): Whether to print log messages to the console.
            debug (bool): Whether to enable debug mode.
            max_workers (int): Maximum number of worker threads or processes to use.
            use_process_pool (bool): Whether to use a process pool instead of a thread pool.
        """
        self.executor.shutdown(wait=False)
        self.__init__(*args, **kwargs)

    def _init_log(self):
        io = open(self.log_file, 'a')
        io.close()

    def submit(self, fn, *args, group="default", **kwargs):
        """
        Submits a task to the executor for execution.

        Args:
            fn: The function to be executed.
            *args: Positional arguments to be passed to the function.
            group: The group to which the task belongs (default is "default").
            **kwargs: Keyword arguments to be passed to the function.
        """
        future = self.executor.submit(fn, *args, **kwargs)
        future.add_done_callback(worker_callbacks)
        if group not in self.tasks:
            self.tasks[group] = []
        self.tasks[group].append(future)

    def get_logs(self):
        """
        Reads the contents of the log file and returns them as a list of lines.

        Raises:
            Exception: If no log file was defined.

        Returns:
            list: A list of lines read from the log file.
        """
        if self.log_file is None:
            raise Exception("No log file was defined")
        with open(self.log_file, 'r') as f:
            return f.readlines()

    def get_queue(self, group='default'):
        return [i.done() for i in self.tasks[group]]

    def info(self, content, **kwargs):
        """ Logs an informational message. """
        self.wlog(content, "[info]")

    def time(self, content):
        """ Logs a time message. """
        self.wlog(content, "[time]")

    def warn(self, content):
        """ Logs a warning message. """
        self.wlog(content, "[warning]")

    def critical(self, content):
        """ Logs a critical message. """
        self.wlog(content, "[critical]")

    def debug(self, content):
        """ Logs a debug message. """
        if self.debug_mode:
            self.wlog(content, "[debug]")

    def wlog(self, content, tipo="[info]", print_log=True):
        func = inspect.currentframe().f_back.f_back.f_code
        function = func.co_name
        filename = func.co_filename
        thread_id = threading.current_thread().native_id
        if tipo == "[critical]":
            log_message = f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}  {tipo} - Thread {thread_id} - {str(content)}"
        elif tipo == "[time]":
            log_message = f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}  {tipo} - {str(content)}"
        else:
            log_message = f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}  {tipo} - {os.path.basename(filename)} - {function}() - {str(content)}"
        if print_log:
            print(log_message, end="\n")
        if self.keep_in_memory:
            self.memory.append(log_message)
        if self.log_file is not None:
            with self.lock:
                with open(self.log_file, 'a') as io:
                    io.write(log_message + "\n")

    def timer(self, func):
        """
        A decorator function that measures the execution time of a given function and writes to the log.

        @control.timer
        def my_function():
            # code goes here
        """
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            final = time.time() - start
            final = round(final, 4)
            self.time(f"{func.__name__}() executed in {final}s")
            return result
        return wrapper

    def wait(self, group="default"):
        """
        Waits for all tasks in the specified group to complete.

        Args:
            group (str, optional): The group name. Defaults to "default".
        """
        if group not in self.tasks:
            return
        queue = [i.done() for i in self.tasks[group]]
        while False in queue:
            time.sleep(0.05)
            queue = [i.done() for i in self.tasks[group]]

    def clear_logs(self):
        """
        Clears the contents of the log file.
        """
        with open(self.log_file, 'w') as io:
            io.close()

def worker_callbacks(f):
    """
    Called to create trace of exceptions in threads.
    """
    e = f.exception()
    if e is None:
        return
    trace = []
    tb = e.__traceback__
    while tb is not None:
        trace.append({
            "filename": tb.tb_frame.f_code.co_filename,
            "name": tb.tb_frame.f_code.co_name,
            "lineno": tb.tb_lineno
        })
        tb = tb.tb_next
    trace_str = ""
    for key, i in enumerate(trace):
        trace_str += f"[Trace {key}: {i['filename']} - {i['name']}() - line {i['lineno']}]"
    control.critical(f"""{type(e).__name__}: {str(e)} -> {trace_str}""")

control = ControlThreads(log_file=None, print_log=True, debug=True)
