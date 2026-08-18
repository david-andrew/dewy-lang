# High Performance Parallelism
TODO: want strong support for high performance parallelism
(see discussion with gemini)
- CPU work stealing algorithm
- user provides functions for: work split, minimum work, result recombining
- GPU task support, user provides kernel
- complect dependent task support via some sort of dependency graph
- high performance distributed support as well. probably completely different set of primitives
- note gemini recommended including simpler concurrency tools like mutexes+channels since some simple non-parallel but concurrent problems are not well suited for the more advanced tools like work-stealing dequeues



# Gemini Discussion Outline

### **Design Document: A Tiered Architecture for High-Performance Parallelism**

**1. Guiding Principle: Abstracting Complexity via Tiered Abstractions**

The core philosophy is to provide programmers with abstractions that match the structure of their problem, while hiding the complex, error-prone mechanics of the underlying hardware. The language will offer a tiered set of tools, from simple "it just works" parallelism for common cases to expert-level control for specialized needs. The default path will always be the safest and most abstract.

---

**2. Tier 1: Foundational CPU Parallelism - The Work-Stealing Scheduler**

This is the engine that will power most CPU-bound parallel operations. Its implementation is internal to the language runtime and not directly exposed to the programmer.

*   **Application:** General-purpose CPU-bound tasks, fork-join parallelism, parallel loops.
*   **Implementation Strategy:**
    *   **Per-Core Deques:** On startup, the runtime creates a pool of worker threads, pinning each to a physical CPU core. Each thread is assigned a double-ended queue (deque).
    *   **LIFO/FIFO Discipline:**
        *   A worker thread pushes new sub-tasks (`fork`) and pops its own work (`join`) from the **bottom** of its deque (LIFO). This is a private, non-atomic, cache-friendly operation.
        *   When a worker runs out of local work, it becomes a "thief" and attempts to pop a task from the **top** of another randomly chosen worker's deque (FIFO).
    *   **Lock-Free Stealing:** The "steal" operation on the top of the deque must be implemented using a lock-free algorithm, relying on a hardware-level **Compare-And-Swap (CAS)** atomic instruction to safely manage the head pointer in the face of concurrent thieves.
    *   **Global Injection Queue:** A single, global, concurrent Multi-Producer/Multi-Consumer (MPMC) queue will exist for submitting initial work from outside the thread pool (e.g., from the main thread or an I/O thread). Workers will check this queue before attempting to steal.

---

**3. Tier 2: High-Level Parallel Constructs (The Programmer's Interface)**

These are the primary tools programmers will use. They are built on top of the Tier 1 scheduler.

**3.1. Embarrassingly Parallel Operations**

*   **Application:** Image processing, scientific computing, data transformation, any problem that can be modeled as "do the same thing to every element in a collection."
*   **Feature:** **Parallel Iterators**
*   **Interface (Pseudocode):**
    ```
    // A standard collection type
    interface Collection<T> {
      // Returns a standard sequential iterator
      iter(): Iterator<T>
      // Returns a parallel iterator, the gateway to parallelism
      par_iter(): ParallelIterator<T>
    }

    interface ParallelIterator<T> {
      // Executes a function for each element in parallel.
      // Blocks until all work is complete.
      for_each(func: (T) -> void): void

      // Creates a new parallel collection by applying a function to each element.
      map<U>(func: (T) -> U): ParallelCollection<U>

      // Reduces the collection to a single value in parallel.
      reduce(identity: T, op: (T, T) -> T): T
    }
    ```
*   **Implementation Strategy:** A call to `par_iter().for_each(...)` is not a simple loop. The implementation recursively splits the collection's range in half. When a range is large enough, it forks the processing of one half as a new task onto the current worker's deque and recursively processes the other half itself. This naturally feeds the work-stealing scheduler.

**3.2. Complex Dependency Graphs**

*   **Application:** Compilers, build systems, game engines, any workflow with irregular, dynamic dependencies.
*   **Feature:** **Futures and Asynchronous Tasks**
*   **Interface (Pseudocode):**
    ```
    // A Future is a handle to a value that may not be ready yet.
    interface Future<T> {
      // Blocks the current *logical task* (not thread) until the value is ready.
      // A worker thread that awaits will drop this task and steal another.
      await(): T

      // Checks if the value is ready without blocking.
      is_ready(): bool
    }

    // The core scheduler interface for dependent tasks.
    interface Scheduler {
      // Schedules a function to run. Returns a Future to its result immediately.
      // The task becomes runnable as soon as its dependencies are met.
      schedule<T>(
        task_func: () -> T,
        dependencies: optional Collection<Future<any>>
      ): Future<T>
    }
    ```
*   **Implementation Strategy:**
    1.  The `Scheduler.schedule` function creates a `Task` object containing the function pointer and a list of dependency Futures. The `Task` is placed in a central graph and marked `Waiting`.
    2.  When a Future is completed, the scheduler iterates through its dependents. If a dependent `Task` has all its dependencies met, its state is changed to `Runnable` and it's pushed to the global injection queue.
    3.  A call to `Future.await()` within a task's logic is a compiler/runtime intrinsic. It registers the current task as `Waiting` on the target Future and signals the worker thread to immediately return to the scheduler to find a new `Runnable` task. It **must not** block the OS thread.

---

**4. Tier 3: Heterogeneous & Distributed Computing**

This tier acknowledges that not all hardware is the same and that computation may span multiple machines. It builds on the concepts of Tiers 1 and 2 but adapts them for different constraints.

**4.1. GPU Co-Processing**

*   **Application:** Highly data-parallel sub-problems within a larger computation (e.g., specific compiler passes, linear algebra, image filtering).
*   **Feature:** **Execution Policies and Kernel Abstraction**
*   **Interface (Pseudocode):**
    ```
    // Extend parallel iterators with an execution policy.
    // The programmer hints at the desired execution environment.
    enum ExecutionPolicy { CPU, GPU_ACCELERATED }

    interface ParallelIterator<T> {
      // New `for_each` with a policy.
      for_each(policy: ExecutionPolicy, func: (T) -> void): void
    }
    ```
*   **Implementation Strategy:**
    *   When `ExecutionPolicy.GPU_ACCELERATED` is used, the runtime attempts to compile the body of the `func` lambda into a GPU kernel (e.g., SPIR-V or PTX).
    *   It inserts boilerplate code to manage memory transfers: `CPU RAM -> GPU VRAM`, kernel execution, and `GPU VRAM -> CPU RAM`.
    *   This is a "leaky abstraction": the programmer is responsible for ensuring the `func` body is GPU-friendly (no divergent control flow, etc.) and that the data size justifies the transfer overhead.
    *   **Indirect Execution:** For advanced cases (like game engines), provide `IndirectDraw` commands that allow the CPU to tell the GPU to chain its own operations without CPU readback, using GPU-side buffers as command arguments.

**4.2. Distributed Tasks**

*   **Application:** Big data processing (e.g., Apache Spark), large-scale scientific simulations.
*   **Feature:** **Resilient Distributed Datasets/DataFrames and Remote Tasks**
*   **Interface (Pseudocode):**
    ```
    // Abstraction for a collection partitioned across a cluster.
    interface DistributedCollection<T> {
      // Transformations build a lineage graph but don't execute yet (lazy).
      map<U>(func: (T) -> U): DistributedCollection<U>
      filter(func: (T) -> bool): DistributedCollection<T>

      // Actions trigger the actual computation across the cluster.
      reduce(op: (T, T) -> T): Future<T>
      collect(): Future<Collection<T>>
    }

    // All functions passed to transformations must be serializable.
    // The language must provide a `Serializable` trait/interface.
    ```
*   **Implementation Strategy:**
    1.  **Lazy Evaluation & Lineage:** Calls to `map` and `filter` do not execute. They build a logical Directed Acyclic Graph (DAG) of the computation's "lineage".
    2.  **Job Scheduler:** A call to an action (`reduce`, `collect`) triggers the central scheduler. It analyzes the DAG, optimizes it, and breaks it into stages of coarse-grained, serializable tasks.
    3.  **Data Locality:** The scheduler queries a cluster manager to find where data partitions live and attempts to send computation to the data.
    4.  **Fault Tolerance:** If a worker node dies, the scheduler uses the lineage graph to re-compute the lost data partitions by re-running the necessary tasks on another available node.
    5.  **RPC & Serialization:** The runtime must have a robust, built-in RPC mechanism and a default serialization protocol.

---

**5. Conclusion: A Graduated Approach to Parallelism**

By structuring the language features in these tiers, we empower all levels of programmers. Novices can achieve significant speedups safely with `par_iter`. Experts can build complex, real-time systems like game engines using the `Future`-based tasking system. And data scientists can scale their analyses to massive clusters, all while thinking in terms of the same core concept: a graph of dependent computations. The language's role is to provide the safest, most abstract tool that can effectively solve the problem at hand.


# Why keep less performant parallelism/concurrency primitives

That's an exceptionally sharp and provocative design question. It gets right to the heart of language philosophy: **Should a language be a "pit of success" by only providing the best tools, or should it be a comprehensive toolbox that includes simpler, sharper tools for specific jobs?**

You are advocating for a highly opinionated language design, and there's a strong argument for it. However, removing mutexes entirely would have significant, and likely negative, consequences.

Let's analyze the pros and cons of this "no mutexes, only high-level parallelism" approach.

---

### The Argument FOR Removing Mutexes (Your Position)

1.  **Forces Good Habits:** By removing the "easy" but often non-performant and deadlock-prone option, the language forces programmers to structure their problems in a way that is amenable to modern parallel patterns (e.g., message passing, structured parallelism). It nudges everyone towards thinking about data ownership and dependency graphs.

2.  **Reduces Language Surface Area:** Fewer concurrency primitives mean less for the language maintainers to implement, document, and perfect. It also means less for a new programmer to learn and potentially misuse.

3.  **Drives API Excellence:** As you said, if the *only* tools are the high-level ones, there is immense pressure to make their APIs incredibly polished, ergonomic, and well-documented, because they must serve everyone from the beginner to the expert.

4.  **Avoids Performance Traps:** Prevents programmers from building a system that works fine with 2 threads, but then grinds to a halt with 16 threads because of lock contention. They are forced to use a scalable solution from day one.

---

### The Strong Argument AGAINST Removing Mutexes

Despite the compelling points above, here's why virtually every language—even those with state-of-the-art parallelism like Rust and Go—keeps mutexes and similar primitives around.

**1. Not All Concurrency is About Parallelism**

This is the most crucial distinction.
*   **Parallelism** is about doing lots of work *faster* by using multiple cores. This is where work-stealing shines.
*   **Concurrency** is about managing lots of *tasks at the same time*, which may or may not be CPU-bound.

**Consider the Motivating Example: The Global Cache.**

In our application, we had a `Mutex<Map<...>>` for a shared picture cache. Let's analyze this problem:
*   **Is it a performance bottleneck?** No. Accessing this cache is infrequent. A thread might grab the lock for a few microseconds once every few seconds. There is virtually zero contention.
*   **Is it a parallelism problem?** No. We don't need to speed up the cache access itself. We just need to ensure that when two threads *happen* to access it at the same time, they do so safely without corrupting the map.

How would you solve this with only high-level tools?

*   **Message Passing / Actor Model:** You could create a dedicated "cache actor" thread that owns the map. Any other thread wanting to access the cache would have to send an asynchronous message (`{ type: 'get', key: '...' }`) and wait for a response message on another channel.

This would work, but it's **enormously overwrought** for this problem. You've replaced a simple, clear `mutex.lock(...)` with a dedicated thread, two channels, and an asynchronous message-passing protocol. The cognitive overhead and boilerplate are significantly higher for a problem that a mutex solves perfectly and efficiently.

**2. Protecting Inevitable "Oddball" Shared State**

Sometimes, you just have a weird, global piece of state that needs to be managed. Initializing a logger, updating a small configuration value, registering a plugin. These are not data-parallel problems. They are simple state-change problems that require synchronization. A mutex is the most direct and readable tool for this job. Forcing it into a complex parallel framework is using a sledgehammer to crack a nut.

**3. Interacting with the Outside World (FFI)**

When your language needs to call into a C library (Foreign Function Interface), that library might require you to hold a lock before calling certain functions. Your language *must* provide a primitive that can satisfy this external requirement. You can't tell the C library to adopt a work-stealing model.

**4. The "Escape Hatch" is Crucial**

High-level abstractions are great, but they aren't perfect for every niche scenario. Sometimes, an expert programmer needs to build a new, custom synchronization primitive or data structure. The fundamental building blocks for those are almost always low-level atomics and, yes, mutexes or condition variables. Removing them takes away the power to build the *next* generation of high-level abstractions.

### Conclusion: The Better Path is "Safe by Default"

Instead of removing mutexes, the modern language design philosophy is to make them **safe to use and less appealing for problems they don't solve well.**

This is the Rust approach:
1.  **Make Mutexes Safe:** `Mutex<T>` is integrated with the ownership system. You cannot forget to unlock it (the lock is released when the guard object goes out of scope). You cannot access the data without holding the lock (this is a compile-time error). This eliminates many common mutex bugs.
2.  **Make Parallelism Easy and Fast:** Provide incredibly ergonomic and performant tools like Rayon's `par_iter()`.

When a programmer is faced with a choice:
*   For a big `for` loop, `par_iter()` is a one-line change and is clearly the right tool.
*   For a simple shared cache, wrapping it in a `Mutex` is straightforward and obviously correct.

The language doesn't *forbid* the simpler tool; it just makes the high-performance tool so easy and attractive for the right problems that people naturally gravitate towards it. It guides them to the "pit of success" without taking away a fundamental and sometimes necessary tool.

So, your hypothetical language should absolutely **not** promote mutexes for high-performance computation. But it should **provide a safe, well-designed Mutex** as a fundamental tool for managing simple shared state, because that is a distinct and valid problem class.