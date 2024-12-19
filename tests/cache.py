from multiprocess import Manager, Process
from logpool import control
import numpy as np

def worker_add(key, array):
    control.add_to_cache(key, array)
    print(f"Added {key}")

def worker_get(key):
    array = control.get_from_cache(key)
    print(f"Retrieved {key}: {'Exists' if array is not None else 'Not Found'}")

if __name__ == "__main__":
    # Example arrays
    img1 = np.random.rand(1024, 1024)
    img2 = np.random.rand(2048, 2048)

    # Create processes
    p1 = Process(target=worker_add, args=("image1", img1))
    p2 = Process(target=worker_get, args=("image1",))

    # Start and join processes
    p1.start()
    p1.join()

    p2.start()
    p2.join()