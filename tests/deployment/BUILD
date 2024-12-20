load("@rules_python//python:defs.bzl", "py_test")

py_test(
    name = "container_test",
    srcs = ["container_test.py"],
    deps = [
        "//feed_processor",
        requirement("pytest"),
        requirement("docker"),
    ],
)

py_test(
    name = "container_scaling_test",
    srcs = ["container_scaling_test.py"],
    deps = [
        "//feed_processor",
        requirement("pytest"),
        requirement("docker"),
        requirement("psutil"),
    ],
)
