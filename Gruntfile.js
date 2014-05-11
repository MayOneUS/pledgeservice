var LOCAL_CONFIG = {
  appName: 'local',
  appVersion: '1',
  hardCodeStripe: true,
  stripePublicKey: 'pk_test_g7UBToGvPpJ1xJa8OVsfV7zf',
  stripePrivateKey: 'sk_test_sm4iLzUFCeEE4l8uKe4KNDU7',
};

var DEV_CONFIG = {
  appName: 'pure-spring-568',
  appVersion: '1',
};

var STAGING_CONFIG = {
  appName: 'mayday-pac',
  appVersion: 'staging',
};

var PROD_CONFIG = {
  appName: 'mayday-pac',
  appVersion: '1',
};

var preprocessAppYaml = function(config) {
  return {
    src : [ 'build/app.yaml' ],
    options: { inline : true, context : config }
  };
};

var createConfigFile = function(config) {
  return {
    "build/config.json": function(fs, fd, done) {
      fs.writeSync(fd, JSON.stringify(config));
      done();
    }
  };
};

module.exports = function(grunt) {
  // configure the tasks
  grunt.initConfig({
    clean: {
      main: {
        src: [ 'build' ],
      },
    },

    copy: {
      main: {
        files: [
          {cwd: 'backend/', src: '**', dest: 'build/', expand: true },
          {cwd: 'assets/', src: '**', dest: 'build/static/', expand: true },
        ],
      },
    },

    preprocess: {
      local : preprocessAppYaml(LOCAL_CONFIG),
      dev: preprocessAppYaml(DEV_CONFIG),
      staging: preprocessAppYaml(STAGING_CONFIG),
      prod: preprocessAppYaml(PROD_CONFIG),
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
        files: [
          {cwd: 'markup/', src: '*.jade.j2', dest: 'build/templates/',
           expand: true, ext: '.html'},
          {cwd: 'markup/', src: '*.jade', dest: 'build/static/', expand: true,
           ext: '.html'},
        ]
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
        command: 'dev_appserver.py --skip_sdk_update_check --host 0.0.0.0 --admin_host 0.0.0.0 build/',
        options: {
          async: true,
        },
      },
    },

    "file-creator": {
      local: createConfigFile(LOCAL_CONFIG),
      dev: createConfigFile(DEV_CONFIG),
      staging: createConfigFile(STAGING_CONFIG),
      prod: createConfigFile(PROD_CONFIG),
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
        tasks: [ 'copy', 'preprocess:local' ]
      }
    },
  });

  // load the tasks
  grunt.loadNpmTasks('grunt-autoprefixer');
  grunt.loadNpmTasks('grunt-contrib-clean');
  grunt.loadNpmTasks('grunt-contrib-copy');
  grunt.loadNpmTasks('grunt-contrib-jade');
  grunt.loadNpmTasks('grunt-contrib-sass');
  grunt.loadNpmTasks('grunt-contrib-watch');
  grunt.loadNpmTasks('grunt-file-creator');
  grunt.loadNpmTasks('grunt-preprocess');
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
    'local',
    'Builds, runs the local dev server, and watches for updates.',
    [ 'build', 'preprocess:local', 'file-creator:local',
      'shell:devserver', 'watch']
  );
  grunt.registerTask('dev', 'Builds for the DEV appengine environment.',
                     [ 'build', 'preprocess:dev', 'file-creator:dev' ]);
  grunt.registerTask('staging', 'Builds for the STAGING appengine environment.',
                     [ 'build', 'preprocess:staging', 'file-creator:staging' ]);
  grunt.registerTask('prod', 'Builds for the PROD appengine environment.',
                     [ 'build', 'preprocess:prod', 'file-creator:prod' ]);
};
