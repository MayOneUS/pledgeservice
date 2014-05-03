module.exports = function(grunt) {
    // configure the tasks
    grunt.initConfig({
        copy: {
            main: {
                files: [
                    {cwd: 'backend/', src: '**', dest: 'build/', expand: true },
                    {cwd: 'assets/', src: '**', dest: 'build/static/', expand: true },
                ],
            },
        },

        clean: {
            main: {
                src: [ 'build' ],
            },
        },

        sass: {
            main: {
                files: {
                    'build/static/style.css': 'stylesheets/style.scss'
                }
            }
        },

        jade: {
            compile: {
                options: {
                    data: {
                        debug: false
                    }
                },
                files: {
                    "build/static/index.html": "markup/index.jade",
                    "build/static/pledge.html": "markup/pledge.jade"
                }
            }
        },

        autoprefixer: {
            build: {
                expand: true,
                cwd: 'build/static/css/',
                src: [ '*.css' ],
                dest: 'build/static/css/'
            }
        },

        shell: {
            devserver: {
                command: 'dev_appserver.py build/',
                options: {
                    async: true,
                },
            },
        },

        watch: {
            stylesheets: {
                files: 'stylesheets/**',
                tasks: [ 'css' ]
            },
            markup: {
                files: 'markup/**',
                tasks: [ 'jade' ]
            },
            copy: {
                files: [ '{js/src,resources,assets,templates,backend}/**' ],
                tasks: [ 'copy' ]
            }
        },
    });

    // load the tasks
    grunt.loadNpmTasks('grunt-autoprefixer');
    grunt.loadNpmTasks('grunt-contrib-clean');
    grunt.loadNpmTasks('grunt-contrib-copy');
    grunt.loadNpmTasks('grunt-contrib-sass');
    grunt.loadNpmTasks('grunt-contrib-watch');
    grunt.loadNpmTasks('grunt-contrib-jade');
    grunt.loadNpmTasks('grunt-shell-spawn');

    // define the tasks
    grunt.registerTask(
        'css', '',
        [ 'sass', 'autoprefixer' ]
    );
    grunt.registerTask(
        'build',
        'Compiles all of the assets and copies the files to the build directory.',
        [ 'clean', 'copy', 'css', 'jade']
    );
    grunt.registerTask(
        'dev',
        'Builds, runs the dev server, and watches for updates.',
        [ 'build', 'shell:devserver', 'watch']
    );
};
