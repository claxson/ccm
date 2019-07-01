# -*- coding: utf-8 -*-

PAYMENTEZ = {"paymentez":
                 {"codes":
                   {"3":
                        {"description":"Paid",
                         "up_status":"AC",
                         "up_recurrence":True,
                         "ph_status":"A",
                         "user_msg":"Pago exitoso",
                         "expire_user":False,
                         "intercom":
                             {"action": True,
                              "event": "approved-pay"
                             }
                         },
                    "6":
                        {"description": "Fraud",
                         "up_status":"CA",
                         "up_recurrence":False,
                         "ph_status":"C",
                         "user_msg":"",
                         "expire_user":False,
                         "intercom":
                             {"action": True,
                              "event": "cancelled-pay"
                             }
                         },
                    "7":
                        {"description": "Refund",
                         "up_status": "CA",
                         "up_recurrence": False,
                         "ph_status": "C",
                         "user_msg": "",
                         "expire_user": False,
                         "intercom":
                             {"action": True,
                              "event": "cancelled-pay"
                              }
                         },
                    "8":
                        {"description": "chargeback",
                         "up_status": "CA",
                         "up_recurrence": False,
                         "ph_status": "C",
                         "user_msg": "",
                         "expire_user": False,
                         "intercom":
                             {"action": True,
                              "event": "cancelled-pay"
                              }
                         },
                    "9":
                        {"description": "rejected by carrier",
                         "up_status":"ER",
                         "up_recurrence":False,
                         "ph_status":"R",
                         "user_msg":"El pago fue rechazado. Por favor consulte con su banco y reintente luego.",
                         "expire_user":False,
                         "intercom":
                             {"action": True,
                              "event": "rejected-pay"
                             }
                         },
                    "10":
                        {"description": "system error",
                         "up_status":"ER",
                         "up_recurrence":False,
                         "ph_status":"R",
                         "user_msg":"Ocurrió un problema en el proceso pago. Por favor, reintente más tarde. "
                                    "Puede consultar a nuestro soporte a soporte@hotgo.tv",
                         "expire_user":False,
                         "intercom":
                             {"action": True,
                              "event": "rejected-pay"
                             }
                         },
                    "11":
                        {"description": "paymentez fraud",
                         "up_status":"ER",
                         "up_recurrence":False,
                         "ph_status":"R",
                         "user_msg":"El pago fue rechazado. Por favor consulte con su banco y reintente luego.",
                         "expire_user":False,
                         "intercom":
                             {"action": True,
                              "event": "rejected-pay"
                             }
                         },
                    "12":
                        {"description": "paymentez blacklist",
                         "up_status":"ER",
                         "up_recurrence":False,
                         "ph_status":"R",
                         "user_msg":"El pago fue rechazado, por favor intente con otra tarjeta.",
                         "expire_user":False,
                         "intercom":
                             {"action": True,
                              "event": "rejected-pay"
                             },
                         },
                    "13":
                        {"description": "time tolerance",
                         "up_status":"ER",
                         "up_recurrence":False,
                         "ph_status":"R",
                         "user_msg":"Ocurrió un problema en el proceso de pago. Por favor, reintente más tarde. "
                                    "Puede consultar a nuestro soporte a soporte@hotgo.tv",
                         "expire_user":False,
                         "intercom":
                             {"action": True,
                              "event": "rejected-pay"
                             }
                        },
                    "19":
                        {"description": "invalid authorization code",
                         "up_status": "ER",
                         "up_recurrence": False,
                         "ph_status": "R",
                         "user_msg": "Ocurrió un error con el pago, por favor "
                                     "consulte con su banco y reintente nuevamente.",
                         "expire_user": False,
                         "intercom":
                             {"action": True,
                              "event": "rejected-pay"
                              }
                         },
                    "20":
                        {"description": "authorization code expired",
                         "up_status": "ER",
                         "up_recurrence": False,
                         "ph_status": "R",
                         "user_msg": "Ocurrió un error con el pago, por favor "
                                     "consulte con su banco y reintente nuevamente.",
                         "expire_user": False,
                         "intercom":
                             {"action": True,
                              "event": "rejected-pay"
                              }
                         },
                    "21":
                        {"description": "paymentez fraud - pending refund",
                         "up_status": "ER",
                         "up_recurrence": False,
                         "ph_status": "R",
                         "user_msg": "Ocurrió un error con el pago, por favor "
                                     "consulte con su banco y reintente nuevamente.",
                         "expire_user": False,
                         "intercom":
                             {"action": True,
                              "event": "rejected-pay"
                              }
                         },
                    "22":
                        {"description": "invalid authcode - pending refund",
                         "up_status": "ER",
                         "up_recurrence": False,
                         "ph_status": "R",
                         "user_msg": "Ocurrió un error con el pago, por favor "
                                     "consulte con su banco y reintente nuevamente.",
                         "expire_user": False,
                         "intercom":
                             {"action": True,
                              "event": "rejected-pay"
                              }
                         },
                    "23":
                        {"description": "authcode expired - pending refund",
                         "up_status": "ER",
                         "up_recurrence": False,
                         "ph_status": "R",
                         "user_msg": "Ocurrió un error con el pago, por favor "
                                     "consulte con su banco y reintente nuevamente.",
                         "expire_user": False,
                         "intercom":
                             {"action": True,
                              "event": "rejected-pay"
                              }
                         },
                    "24":
                        {"description": "paymentez fraud - refund request",
                         "up_status": "ER",
                         "up_recurrence": False,
                         "ph_status": "R",
                         "user_msg": "Ocurrió un error con el pago, por favor "
                                     "consulte con su banco y reintente nuevamente.",
                         "expire_user": False,
                         "intercom":
                             {"action": True,
                              "event": "rejected-pay"
                              }
                         },
                    "25":
                        {"description": "invalid authcode - refund requested",
                         "up_status": "ER",
                         "up_recurrence": False,
                         "ph_status": "R",
                         "user_msg": "Ocurrió un error con el pago, por favor "
                                     "consulte con su banco y reintente nuevamente.",
                         "expire_user": False,
                         "intercom":
                             {"action": True,
                              "event": "rejected-pay"
                              }
                         },
                    "26":
                        {"description": "authcode expired - refund requested",
                         "up_status": "ER",
                         "up_recurrence": False,
                         "ph_status": "R",
                         "user_msg": "Ocurrió un error con el pago, por favor "
                                     "consulte con su banco y reintente nuevamente.",
                         "expire_user": False,
                         "intercom":
                             {"action": True,
                              "event": "rejected-pay"
                              }
                         },
                    "27":
                        {"description": "merchant - pending refund.",
                         "up_status": "ER",
                         "up_recurrence": False,
                         "ph_status": "C",
                         "user_msg": "",
                         "expire_user": False,
                         "intercom":
                             {"action": True,
                              "event": "cancelled-pay"
                              }
                         },
                    "28":
                        {"description": "merchant - refund requested",
                         "up_status": "ER",
                         "up_recurrence": False,
                         "ph_status": "C",
                         "user_msg": "",
                         "expire_user": False,
                         "intercom":
                             {"action": True,
                              "event": "cancelled-pay"
                              }
                         },
                    "29":
                        {"description": "annuled",
                         "up_status": "ER",
                         "up_recurrence": False,
                         "ph_status": "C",
                         "user_msg": "",
                         "expire_user": False,
                         "intercom":
                             {"action": True,
                              "event": "cancelled-pay"
                              }
                         },
                    "30":
                        {"description": "transaction seated (only datafast)",
                         "up_status": "AC",
                         "up_recurrence": False,
                         "ph_status": "A",
                         "user_msg": "",
                         "expire_user": False,
                         "intercom":
                             {"action": True,
                              "event": "approved-pay"
                              }
                         },
                    "-1":{"description": "response error",
                         "up_status": "ER",
                         "up_recurrence": False,
                         "ph_status": "E",
                         "user_msg": "Ocurrió un error con el pago, por favor reintente nuevamente más tarde",
                         "expire_user": False,
                         "intercom":
                             {"action": False,
                              "event": "rejected-pay"
                              }
                        },
                    "-10":
                        {"description":"Paid",
                         "up_status":"AC",
                         "up_recurrence":True,
                         "ph_status":"A",
                         "user_msg":"Pago exitoso con descuento del 100%",
                         "expire_user":False,
                         "intercom":
                             {"action": True,
                              "event": "approved-pay"
                             }
                         }
                        }
                    }
                 }

PAGODIGITAL =  {"codes":
                    {"00":
                        {"description":"Aprobado",
                        "up_status":"AC",
                        "up_recurrence":True,
                        "ph_status":"A",
                        "user_msg":"Pago exitoso",
                        "expire_user":False,
                        "intercom":
                            {"action": True,
                            "event": "approved-pay"
                            }
                        },
                    "51":
                        {"description":"Fondos insuficientes",
                        "up_status":"ER",
                        "up_recurrence":False,
                        "ph_status":"E",
                        "user_msg":"Ocurrió un error con el pago, por favor comuniquese con su banco y reintente nuevamente más tarde",
                        "expire_user":False,
                        "intercom":
                            {"action": True,
                            "event": "rejected-pay"
                            }
                        },
                    "-1":{"description": "response error",
                         "up_status": "ER",
                         "up_recurrence": False,
                         "ph_status": "E",
                         "user_msg": "Ocurrió un error con el pago, por favor reintente nuevamente más tarde",
                         "expire_user": False,
                         "intercom":
                             {"action": True,
                              "event": "rejected-pay"
                              }
                        },
                    "-10":
                        {"description":"Paid",
                         "up_status":"AC",
                         "up_recurrence":True,
                         "ph_status":"A",
                         "user_msg":"Pago exitoso con descuento del 100%",
                         "expire_user":False,
                         "intercom":
                             {"action": True,
                              "event": "approved-pay"
                             }
                        }    
                    }
                }    