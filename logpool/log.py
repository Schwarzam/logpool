from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import threading
import inspect
import os
from datetime import datetime
import time
import psutil
from threading import Lock
from collections import OrderedDict
from multiprocessing import shared_memory, Lock
import numpy as np

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
        debug_mode=False, 
        max_workers=psutil.cpu_count(logical=True) - 2, 
        use_process_pool=False,
        keep_in_memory=False,
        simple_log=False,
        callback=None,
        max_cache_memory=100_000 # max cache memory in bytes
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
        self.debug_mode = debug_mode
        self.use_process_pool = use_process_pool
        self.simple_log = simple_log
        self.callback = callback
        
        self.keep_in_memory = keep_in_memory
        self.log_memory = []
        
        
        self.thread_results = {'default': []}
        
        self.executor = ProcessPoolExecutor(max_workers) if use_process_pool else ThreadPoolExecutor(max_workers)

        self.cache = OrderedDict()  # Cache to store shared memory references of numpy arrays
        self.max_cache_memory = max_cache_memory  # Max memory in bytes
        self.current_memory = 0  # Current memory usage in bytes
        self.lock = Lock()  # Lock for thread/process safety
    
    def change_pool(self, process_pool=False):
        """
        Changes the pool type to either a thread pool or a process pool.

        Args:
            process_pool (bool): Whether to use a process pool.
        """
        self.executor.shutdown(wait=False)
        self.use_process_pool = process_pool
        
        self.executor = ProcessPoolExecutor(self.workers) if process_pool else ThreadPoolExecutor(self.workers)
    
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

        Returns:
            Future: The Future object representing the task.
        """
        future = self.executor.submit(fn, *args, **kwargs)
        future.add_done_callback(worker_callbacks)
        
        if group not in self.tasks:
            self.tasks[group] = []
            self.thread_results[group] = []
        
        self.tasks[group].append(future)
        return future

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
        
        log_message = f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}  "
        
        if tipo == "[critical]":
            log_message += f"{tipo} - Thread {thread_id} - {str(content)}"
        elif tipo == "[time]":
            log_message += f"{tipo} - {str(content)}"
        else:
            if self.simple_log:
                log_message = f"{tipo} - {str(content)}"
            else:
                log_message += f"{tipo} - {thread_id} - {os.path.basename(filename)} - {function}() - {str(content)}"
        if print_log:
            print(log_message, end="\n")
        if self.keep_in_memory:
            self.log_memory.append(log_message)
        if self.log_file is not None:
            with self.lock:
                with open(self.log_file, 'a') as io:
                    io.write(log_message + "\n")
        
        if self.callback is not None:
            self.callback(log_message)

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
        for future in self.tasks[group]:
            if not future.done():
                future.result()  # Blocks until the task is done
            
            # Append the result if completed successfully
            if future not in self.thread_results[group]:
                if future.exception() is None:
                    self.thread_results[group].append(future.result())
                else:
                    self.critical(f"Error in task: {future.exception()}")

    def get_results(self, group="default"):
        """
        Retrieves the results of tasks in a specified group.

        Args:
            group (str): The group name.

        Returns:
            list: A list of results from completed tasks.
        """
        if group not in self.thread_results:
            return []
        return self.thread_results[group]

    def clear_results(self, group="default"):
        """
        Clears the stored results for a specific group.

        Args:
            group (str): The group name.
        """
        if group in self.thread_results:
            self.thread_results[group] = []
    
    def clear_logs(self):
        """
        Clears the contents of the log file.
        """
        with open(self.log_file, 'w') as io:
            io.close()
    
    
    def _get_memory_size(self, array):
        """Get size of a numpy array in MB."""
        return array.nbytes / (1024 * 1024)

    def add_to_cache(self, key, array):
        """Add a numpy array to the shared memory cache."""
        with self.lock:
            array_memory = self._get_memory_size(array)

            # Check if the array can ever fit in the cache
            if array_memory > self.max_cache_memory:
                print(f"Warning: Array {key} is too large for the cache. Skipping.")
                return

            # Evict items until there's enough space
            while self.current_memory + array_memory > self.max_cache_memory:
                self._evict()

            # Create shared memory
            shm = shared_memory.SharedMemory(create=True, size=array.nbytes)
            shared_array = np.ndarray(array.shape, dtype=array.dtype, buffer=shm.buf)
            shared_array[:] = array[:]  # Copy data into shared memory

            # Add to cache
            self.cache[key] = {
                "shm_name": shm.name,
                "shape": array.shape,
                "dtype": array.dtype,
            }
            self.current_memory += array_memory
            
    def _evict(self):
        """Evict the least recently used (LRU) item from the cache."""
        if not self.cache:
            raise RuntimeError("Cannot evict from an empty cache. The new item might be too large for the cache.")

        key, data = self.cache.popitem(last=False)  # Remove the oldest (LRU) item
        shm = shared_memory.SharedMemory(name=data["shm_name"])
        shm.close()
        shm.unlink()
        self.current_memory -= self._get_memory_size(
            np.zeros(data["shape"], dtype=data["dtype"])
        )

    def get_from_cache(self, key):
        """Retrieve a numpy array from the shared memory cache."""
        with self.lock:
            if key not in self.cache:
                return None

            # Update LRU order
            data = self.cache.pop(key)
            self.cache[key] = data

            # Access shared memory
            shm = shared_memory.SharedMemory(name=data["shm_name"])
            return np.ndarray(data["shape"], dtype=data["dtype"], buffer=shm.buf)

    def clear_cache(self):
        """Clear all shared memory from the cache."""
        with self.lock:
            for data in self.cache.values():
                shm = shared_memory.SharedMemory(name=data["shm_name"])
                shm.close()
                shm.unlink()
            self.cache.clear()
            self.current_memory = 0

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

control = ControlThreads(log_file=None, print_log=True, debug_mode=False)
