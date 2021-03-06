from pythonforandroid.toolchain import Recipe, shprint, shutil, current_directory
from os.path import join, exists
from os import environ
import sh

"""
This recipe creates a custom toolchain and bootstraps Boost from source to build Boost.Build
including python bindings
"""


class BoostRecipe(Recipe):
    # Todo: make recipe compatible with all p4a architectures
    '''
    .. note:: This recipe can be built only against API 21+ and arch armeabi-v7a

    .. versionchanged:: 0.6.0
         Rewrote recipe to support clang's build. The following changes has
         been made:

            - Bumped version number to 1.68.0
            - Better version handling for url
            - Added python 3 compatibility
            - Default compiler for ndk's toolchain set to clang
            - Python version will be detected via user-config.jam
            - Changed stl's lib from ``gnustl_shared`` to ``c++_shared``
    '''
    version = '1.68.0'
    url = 'http://downloads.sourceforge.net/project/boost/' \
          'boost/{version}/boost_{version_underscore}.tar.bz2'
    depends = [('python2', 'python3')]
    patches = ['disable-so-version.patch',
               'use-android-libs.patch',
               'fix-android-issues.patch']

    @property
    def versioned_url(self):
        if self.url is None:
            return None
        return self.url.format(
            version=self.version,
            version_underscore=self.version.replace('.', '_'))

    def should_build(self, arch):
        return not exists(join(self.get_build_dir(arch.arch), 'b2'))

    def prebuild_arch(self, arch):
        super(BoostRecipe, self).prebuild_arch(arch)
        env = self.get_recipe_env(arch)
        with current_directory(self.get_build_dir(arch.arch)):
            if not exists(env['CROSSHOME']):
                # Make custom toolchain
                bash = sh.Command('bash')
                shprint(bash, join(self.ctx.ndk_dir, 'build/tools/make-standalone-toolchain.sh'),
                        '--arch=' + env['ARCH'],
                        '--platform=android-' + str(self.ctx.android_api),
                        '--toolchain=' + env['CROSSHOST'] + '-' + self.ctx.toolchain_version + ':-llvm',
                        '--use-llvm',
                        '--stl=libc++',
                        '--install-dir=' + env['CROSSHOME']
                        )
            # Set custom configuration
            shutil.copyfile(join(self.get_recipe_dir(), 'user-config.jam'),
                            join(env['BOOST_BUILD_PATH'], 'user-config.jam'))

    def build_arch(self, arch):
        super(BoostRecipe, self).build_arch(arch)
        env = self.get_recipe_env(arch)
        env['PYTHON_HOST'] = self.ctx.hostpython
        with current_directory(self.get_build_dir(arch.arch)):
            # Compile Boost.Build engine with this custom toolchain
            bash = sh.Command('bash')
            shprint(bash, 'bootstrap.sh')  # Do not pass env
        # Install app stl
        shutil.copyfile(
            join(self.ctx.ndk_dir, 'sources/cxx-stl/llvm-libc++/libs/'
                                   'armeabi-v7a/libc++_shared.so'),
            join(self.ctx.get_libs_dir(arch.arch), 'libc++_shared.so'))

    def select_build_arch(self, arch):
        return arch.arch.replace('eabi-v7a', '').replace('eabi', '')

    def get_recipe_env(self, arch):
        # We don't use the normal env because we
        # are building with a standalone toolchain
        env = environ.copy()

        env['BOOST_BUILD_PATH'] = self.get_build_dir(arch.arch)  # find user-config.jam
        env['BOOST_ROOT'] = env['BOOST_BUILD_PATH']  # find boost source

        env['PYTHON_ROOT'] = self.ctx.python_recipe.link_root(arch.arch)
        env['PYTHON_INCLUDE'] = self.ctx.python_recipe.include_root(arch.arch)
        env['PYTHON_MAJOR_MINOR'] = self.ctx.python_recipe.version[:3]
        env['PYTHON_LINK_VERSION'] = self.ctx.python_recipe.major_minor_version_string
        if 'python3' in self.ctx.python_recipe.name:
            env['PYTHON_LINK_VERSION'] += 'm'

        env['ARCH'] = self.select_build_arch(arch)
        env['CROSSHOST'] = env['ARCH'] + '-linux-androideabi'
        env['CROSSHOME'] = join(env['BOOST_ROOT'], 'standalone-' + env['ARCH'] + '-toolchain')
        return env


recipe = BoostRecipe()
