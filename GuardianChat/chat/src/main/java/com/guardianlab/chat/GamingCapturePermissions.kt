package com.guardianlab.chat

import android.Manifest
import android.webkit.PermissionRequest

/** Request only the device permission needed by this same-origin capture request. */
internal object GamingCapturePermissions {
 fun required(resources: Array<String>): Array<String>? {
  if (resources.isEmpty() || resources.any { it != PermissionRequest.RESOURCE_VIDEO_CAPTURE && it != PermissionRequest.RESOURCE_AUDIO_CAPTURE }) return null
  return resources.map { if (it == PermissionRequest.RESOURCE_VIDEO_CAPTURE) Manifest.permission.CAMERA else Manifest.permission.RECORD_AUDIO }.distinct().toTypedArray()
 }
}
