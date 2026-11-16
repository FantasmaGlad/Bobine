package com.bobine.app

import org.json.JSONObject

internal fun bridgeError(code: String, message: String): String =
    JSONObject().put("error", code).put("message", message).toString()

internal fun bridgeOk(extra: JSONObject = JSONObject()): String = extra.put("ok", true).toString()
