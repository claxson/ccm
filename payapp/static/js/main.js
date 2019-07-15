/******/ (function(modules) { // webpackBootstrap
/******/        // The module cache
/******/        var installedModules = {};
/******/
/******/        // The require function
/******/        function __webpack_require__(moduleId) {
/******/
/******/                // Check if module is in cache
/******/                if(installedModules[moduleId]) {
/******/                        return installedModules[moduleId].exports;
/******/                }
/******/                // Create a new module (and put it into the cache)
/******/                var module = installedModules[moduleId] = {
/******/                        i: moduleId,
/******/                        l: false,
/******/                        exports: {}
/******/                };
/******/
/******/                // Execute the module function
/******/                modules[moduleId].call(module.exports, module, module.exports, __webpack_require__);
/******/
/******/                // Flag the module as loaded
/******/                module.l = true;
/******/
/******/                // Return the exports of the module
/******/                return module.exports;
/******/        }
/******/
/******/
/******/        // expose the modules object (__webpack_modules__)
/******/        __webpack_require__.m = modules;
/******/
/******/        // expose the module cache
/******/        __webpack_require__.c = installedModules;
/******/
/******/        // define getter function for harmony exports
/******/        __webpack_require__.d = function(exports, name, getter) {
/******/                if(!__webpack_require__.o(exports, name)) {
/******/                        Object.defineProperty(exports, name, { enumerable: true, get: getter });
/******/                }
/******/        };
/******/
/******/        // define __esModule on exports
/******/        __webpack_require__.r = function(exports) {
/******/                if(typeof Symbol !== 'undefined' && Symbol.toStringTag) {
/******/                        Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' });
/******/                }
/******/                Object.defineProperty(exports, '__esModule', { value: true });
/******/        };
/******/
/******/        // create a fake namespace object
/******/        // mode & 1: value is a module id, require it
/******/        // mode & 2: merge all properties of value into the ns
/******/        // mode & 4: return value when already ns object
/******/        // mode & 8|1: behave like require
/******/        __webpack_require__.t = function(value, mode) {
/******/                if(mode & 1) value = __webpack_require__(value);
/******/                if(mode & 8) return value;
/******/                if((mode & 4) && typeof value === 'object' && value && value.__esModule) return value;
/******/                var ns = Object.create(null);
/******/                __webpack_require__.r(ns);
/******/                Object.defineProperty(ns, 'default', { enumerable: true, value: value });
/******/                if(mode & 2 && typeof value != 'string') for(var key in value) __webpack_require__.d(ns, key, function(key) { return value[key]; }.bind(null, key));
/******/                return ns;
/******/        };
/******/
/******/        // getDefaultExport function for compatibility with non-harmony modules
/******/        __webpack_require__.n = function(module) {
/******/                var getter = module && module.__esModule ?
/******/                        function getDefault() { return module['default']; } :
/******/                        function getModuleExports() { return module; };
/******/                __webpack_require__.d(getter, 'a', getter);
/******/                return getter;
/******/        };
/******/
/******/        // Object.prototype.hasOwnProperty.call
/******/        __webpack_require__.o = function(object, property) { return Object.prototype.hasOwnProperty.call(object, property); };
/******/
/******/        // __webpack_public_path__
/******/        __webpack_require__.p = "";
/******/
/******/
/******/        // Load entry module and return exports
/******/        return __webpack_require__(__webpack_require__.s = "./src/app.js");
/******/ })
/************************************************************************/
/******/ ({

/***/ "./src/app.js":
/*!********************!*\
  !*** ./src/app.js ***!
  \********************/
/*! no exports provided */
/***/ (function(module, __webpack_exports__, __webpack_require__) {

"use strict";
eval("__webpack_require__.r(__webpack_exports__);\n/* harmony import */ var _scss_app_scss__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! ./scss/app.scss */ \"./src/scss/app.scss\");\n/* harmony import */ var _scss_app_scss__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(_scss_app_scss__WEBPACK_IMPORTED_MODULE_0__);\n/**\n * @todo Chequear validación de teléfono\n */\n\n\n\nlet app = new Object();\n\napp.config = {\n  languaje: 'es',\n  country: 'co',\n  source: window.base_url + 'static/pagodigital/data/co.json'\n  // source: 'data/co.json'\n};\n\napp.creditCard = new Cleave('#cc_num', {\n  creditCard: true,\n  creditCardStrictMode: false,\n  onCreditCardTypeChanged: type => {\n    let creditCardInput = $('#cc_num');\n\n    app.creditCard = {};\n\n    switch (type) {\n      case 'unknown':\n        creditCardInput.removeClass('amex diners mastercard visa');\n        break;\n      case 'amex':\n        creditCardInput.addClass('amex');\n        app.creditCard = {\n          number_size: 15 + 2,\n          franchise_name: 'amex',\n          franchise_id: 30\n        };\n        app.cc_cvv.properties.blocks = [4]\n        break;\n      case 'diners':\n        creditCardInput.addClass('diners');\n        app.creditCard = {\n          number_size: 14 + 2,\n          franchise_name: 'diners',\n          franchise_id: 34\n        };\n        app.cc_cvv.properties.blocks = [3]\n        break;\n      case 'mastercard':\n        creditCardInput.addClass('mastercard');\n        app.creditCard = {\n          number_size: 16 + 3,\n          franchise_name: 'mastercard',\n          franchise_id: 91\n        };\n        app.cc_cvv.properties.blocks = [3]\n        break;\n      case 'visa':\n        creditCardInput.addClass('visa');\n        app.creditCard = {\n          number_size: 16 + 3,\n          franchise_name: 'visa',\n          franchise_id: 90\n        };\n        app.cc_cvv.properties.blocks = [3]\n        break;\n    }\n  }\n});\n\napp.expirationNumber = new Cleave('#cc_expiration', {\n  date: true,\n  datePattern: ['m', 'y'],\n  dateMin: moment().format('YYYY-MM-DD'),\n  onValueChanged: element => {\n    if (element.target.value.length > 3) {\n      let year = element.target.value.split('/');\n\n      if (year[1] < moment().format('YY')) {\n        console.log('Error en fecha de expiración');\n      }\n    }\n  }\n});\n\napp.phoneNumber = new Cleave('#phone', {\n  phone: true,\n  phoneRegionCode: 'CO'\n});\n\napp.cc_cvv = new Cleave('#cc_cvv', {\n  blocks: [3]\n});\n\napp.autoComplete = prm => {\n  $.ajax({\n    url: prm.source,\n    success: data => {\n      typeAhead(data);\n    }\n  });\n\n  function typeAhead(data) {\n    let cityList;\n\n    $.each(data, (_index, element) => {\n      if (prm.city == element.departamento) {\n        cityList = element.ciudades;\n      }\n    });\n\n    if (cityList.length == 1) {\n      $(prm.input)\n        .val(cityList)\n        .attr('readonly', true)\n        .addClass('pd-control-valid')\n        .removeClass('pd-control-invalid');\n    } else {\n      let engine = new Bloodhound({\n        local: cityList,\n        queryTokenizer: Bloodhound.tokenizers.whitespace,\n        datumTokenizer: Bloodhound.tokenizers.whitespace\n      });\n\n      engine\n        .clear()\n        .clearPrefetchCache()\n        .clearRemoteCache()\n        .initialize(true);\n\n      $(prm.input)\n        .typeahead(\n          {\n            minLength: 2,\n            highlight: true\n          },\n          {\n            name: 'cities',\n            source: engine\n          }\n        )\n        .on('change blur', function () {\n          let match = false;\n\n          $.each(engine.index.datums, function (index) {\n            if ($(prm.input).val() == index) {\n              match = true;\n            }\n          });\n\n          if (!match) {\n            $(this)\n              .removeClass('pd-control-valid')\n              .val('');\n          } else {\n            $(this).addClass('pd-control-valid');\n          }\n        });\n    }\n  }\n};\n\napp.dropDown = prm => {\n  let input = $(prm.input);\n  let source = prm.source;\n\n  $.ajax({\n    url: source,\n    success: resp => {\n      let statesList = [];\n\n      $.each(resp, (_index, element) => {\n        statesList.push(element.departamento);\n      });\n\n      $.each(statesList, (_index, element) => {\n        input.append(`<option value='${element}'>${element}</option>`);\n      });\n    }\n  });\n};\n\napp.formValidation = _event => {\n  validate.extend(validate.validators.datetime, {\n    parse: function (value) {\n      return moment(value, 'MM/YY').utc();\n    },\n    format: function (value) {\n      return moment()\n        .utc(value)\n        .format('MM/YY');\n    }\n  });\n\n  let constraints = {\n    name: {\n      presence: true,\n      length: {\n        minimum: 3,\n        maximum: 30\n      }\n    },\n    email: {\n      email: true,\n      presence: true\n    },\n    cc_num: {\n      presence: true,\n      length: value => {\n        if (value) {\n          if (value.length > 15) {\n            return { is: app.creditCard.number_size };\n          } else {\n            return { is: 14 };\n          }\n        }\n      }\n    },\n    cc_expiration: {\n      presence: true,\n      datetime: {\n        dateOnly: false,\n        earliest: moment().utc()\n      }\n    },\n    cc_cvv: {\n      presence: true,\n      length: value => {\n        if (value && app.creditCard.number_size) {\n          if (app.creditCard.franchise_name == 'amex') {\n            return { is: 4 };\n          } else {\n            return { is: 3 };\n          }\n        } else {\n          return false;\n        }\n      }\n    },\n    id_card: {\n      presence: true,\n      numericality: true\n    },\n    state: {\n      presence: true\n    },\n    city: {\n      presence: true\n    },\n    address: {\n      presence: true\n    },\n    phone: {\n      presence: false,\n      numericality: true\n    }\n  };\n\n  let form = document.querySelector('form#payment_form');\n  let values = validate.collectFormValues(form);\n  let errors = validate(values, constraints);\n\n  function showErrors(form, errors) {\n    $.each(\n      form.querySelectorAll('input[name], select[name]'),\n      (_index, input) => {\n        showErrorsForInput(input, errors);\n      }\n    );\n  }\n\n  function showErrorsForInput(input, errors) {\n    if (errors) {\n      $.each(errors, index => {\n        if (index == input.name) {\n          $('#' + input.name).addClass('pd-control-invalid');\n        } else {\n          $('#' + input.name).addClass('pd-control-valid');\n        }\n      });\n    }\n  }\n\n  if (errors) {\n    showErrors(form, errors);\n  } else {\n    if (values.cc_expiration) {\n      var expiration = values.cc_expiration.split('/');\n    }\n\n    let current_url = window.location.href;\n    let oUrl = new URL(current_url);\n    let token = oUrl.searchParams.get('token');\n    let user_id = oUrl.searchParams.get('user_id');\n\n    let customParams = {\n      cc_fr_name: app.creditCard.franchise_name,\n      cc_fr_number: app.creditCard.franchise_id,\n      cc_exp_month: expiration[0],\n      cc_exp_year: expiration[1],\n      user_id: user_id,\n      token: token,\n      // cc_number: $('#cc_num').val().replace(/ /g, '')\n      cc_number: app.cc_cvv.getRawValue()\n    };\n\n    $.each(customParams, (index, element) => {\n      $('#' + index).val(element);\n    });\n\n    $.ajax({\n      type: 'POST',\n      data: $('#payment_form').serialize()\n    }).done(resp => {\n      document.write(resp.toString().replace(/ /g, ''));\n    });\n  }\n};\n\n$(document).ready(() => {\n  app.dropDown({\n    input: '#state',\n    source: app.config.source\n  });\n\n  $('#state').on('change', function () {\n    $(this).addClass('pd-control-valid');\n\n    app.autoComplete({\n      city: $(this).val(),\n      input: '#city',\n      source: app.config.source\n    });\n\n    $('#city')\n      .val('')\n      .removeAttr('readonly');\n  });\n\n  $('#payment_form').submit(e => {\n    e.preventDefault();\n    app.formValidation(e);\n  });\n\n  $('input, select').on('change', function () {\n    if ($(this).val() != '') {\n      $(this)\n        .removeClass('pd-control-invalid')\n        .addClass('pd-control-valid');\n    } else {\n      $(this)\n        .removeClass('pd-control-valid')\n    }\n  });\n});\n\n\n//# sourceURL=webpack:///./src/app.js?");

/***/ }),

/***/ "./src/scss/app.scss":
/*!***************************!*\
  !*** ./src/scss/app.scss ***!
  \***************************/
/*! no static exports found */
/***/ (function(module, exports, __webpack_require__) {

eval("// extracted by mini-css-extract-plugin\n\n//# sourceURL=webpack:///./src/scss/app.scss?");

/***/ })

/******/ });