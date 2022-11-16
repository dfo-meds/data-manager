This namespace package is reserved for plugins. Third parties can contribute
plugins by creating the following directory structure in their Python source
root:

    |- pipeman
    |  |- plugins
    |  |  |- your_plugin_name
    |  |  |  |- __init__.py

Do NOT put an `__init__.py` file in either the `pipeman` or `plugins` directory.

In your `__init__.py` file, you can then register your plugin content as needed.

