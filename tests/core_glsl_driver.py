"""Compile generated GLSL with a real GLES driver, without a window or browser."""
import ctypes as c
from ctypes.util import find_library


class DriverUnavailable(RuntimeError):
    pass


def bind(library, name, result, *arguments):
    function = getattr(library, name)
    function.restype = result
    function.argtypes = arguments
    return function


class ShaderDriver:
    def __init__(self):
        egl_name, gl_name = find_library('EGL'), find_library('GLESv2')
        if not egl_name or not gl_name:
            raise DriverUnavailable('EGL and GLES libraries are needed for shader validation')
        self.egl, self.gl = c.CDLL(egl_name), c.CDLL(gl_name)
        pointer, integer, unsigned = c.c_void_p, c.c_int, c.c_uint
        integers = c.POINTER(integer)
        get_proc = bind(self.egl, 'eglGetProcAddress', pointer, c.c_char_p)
        address = get_proc(b'eglGetPlatformDisplayEXT')
        if not address:
            raise DriverUnavailable('Surfaceless EGL is unavailable')
        get_display = c.CFUNCTYPE(pointer, unsigned, pointer, integers)(address)
        self.display = get_display(0x31DD, None, None)  # EGL_PLATFORM_SURFACELESS_MESA
        initialize = bind(self.egl, 'eglInitialize', unsigned, pointer, integers, integers)
        if not self.display or not initialize(self.display, None, None):
            raise DriverUnavailable('Cannot initialize a surfaceless EGL display')
        self.surface = self.context = None
        self.make_current = bind(self.egl, 'eglMakeCurrent', unsigned, pointer, pointer, pointer, pointer)
        self.destroy_context = bind(self.egl, 'eglDestroyContext', unsigned, pointer, pointer)
        self.destroy_surface = bind(self.egl, 'eglDestroySurface', unsigned, pointer, pointer)
        self.terminate = bind(self.egl, 'eglTerminate', unsigned, pointer)
        try:
            bind(self.egl, 'eglBindAPI', unsigned, unsigned)(0x30A0)  # OpenGL ES
            attributes = (integer * 5)(0x3033, 1, 0x3040, 0x40, 0x3038)  # pbuffer, ES3
            config, count = pointer(), integer()
            choose = bind(self.egl, 'eglChooseConfig', unsigned, pointer, integers, c.POINTER(pointer), integer, integers)
            if not choose(self.display, attributes, c.byref(config), 1, c.byref(count)) or count.value != 1:
                raise DriverUnavailable('No GLES3 pbuffer configuration')
            create_surface = bind(self.egl, 'eglCreatePbufferSurface', pointer, pointer, pointer, integers)
            self.surface = create_surface(self.display, config, (integer * 5)(0x3057, 1, 0x3056, 1, 0x3038))
            create_context = bind(self.egl, 'eglCreateContext', pointer, pointer, pointer, pointer, integers)
            self.context = create_context(self.display, config, None, (integer * 3)(0x3098, 3, 0x3038))
            if not self.context or not self.surface or not self.make_current(self.display, self.surface, self.surface, self.context):
                raise DriverUnavailable('Cannot create a GLES3 context')
        except Exception:
            self.close()
            raise
        self.create_shader = bind(self.gl, 'glCreateShader', unsigned, unsigned)
        self.source = bind(self.gl, 'glShaderSource', None, unsigned, integer, c.POINTER(c.c_char_p), integers)
        self.compile_shader = bind(self.gl, 'glCompileShader', None, unsigned)
        self.shader_status = bind(self.gl, 'glGetShaderiv', None, unsigned, unsigned, integers)
        self.shader_log = bind(self.gl, 'glGetShaderInfoLog', None, unsigned, integer, integers, pointer)
        self.delete_shader = bind(self.gl, 'glDeleteShader', None, unsigned)
        self.create_program = bind(self.gl, 'glCreateProgram', unsigned)
        self.attach = bind(self.gl, 'glAttachShader', None, unsigned, unsigned)
        self.link = bind(self.gl, 'glLinkProgram', None, unsigned)
        self.program_status = bind(self.gl, 'glGetProgramiv', None, unsigned, unsigned, integers)
        self.program_log = bind(self.gl, 'glGetProgramInfoLog', None, unsigned, integer, integers, pointer)
        self.delete_program = bind(self.gl, 'glDeleteProgram', None, unsigned)

    def validate(self, vertex, fragment):
        shaders = []
        program = self.create_program()
        try:
            for kind, text in [(0x8B31, vertex), (0x8B30, fragment)]:
                shader = self.create_shader(kind)
                shaders.append(shader)
                encoded = c.c_char_p(text.encode())
                self.source(shader, 1, c.byref(encoded), None)
                self.compile_shader(shader)
                status = c.c_int()
                self.shader_status(shader, 0x8B81, c.byref(status))
                log = c.create_string_buffer(16384)
                self.shader_log(shader, len(log), None, log)
                assert status.value, log.value.decode(errors='replace') + '\n' + text
                self.attach(program, shader)
            self.link(program)
            status = c.c_int()
            self.program_status(program, 0x8B82, c.byref(status))
            log = c.create_string_buffer(16384)
            self.program_log(program, len(log), None, log)
            assert status.value, log.value.decode(errors='replace')
        finally:
            self.delete_program(program)
            for shader in shaders:
                self.delete_shader(shader)

    def close(self):
        self.make_current(self.display, None, None, None)
        if self.context:
            self.destroy_context(self.display, self.context)
        if self.surface:
            self.destroy_surface(self.display, self.surface)
        self.terminate(self.display)
