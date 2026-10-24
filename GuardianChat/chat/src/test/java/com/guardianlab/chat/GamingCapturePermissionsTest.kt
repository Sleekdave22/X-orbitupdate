package com.guardianlab.chat

import android.Manifest
import android.webkit.PermissionRequest
import org.junit.Assert.*
import org.junit.Test

class GamingCapturePermissionsTest {
 @Test fun cameraEvidenceDoesNotRequestMicrophone() {
  assertArrayEquals(arrayOf(Manifest.permission.CAMERA), GamingCapturePermissions.required(arrayOf(PermissionRequest.RESOURCE_VIDEO_CAPTURE)))
 }
 @Test fun silentVirtualCameraDoesNotRequireMicrophone() {
  assertFalse(GamingCapturePermissions.required(arrayOf(PermissionRequest.RESOURCE_VIDEO_CAPTURE))!!.contains(Manifest.permission.RECORD_AUDIO))
 }
 @Test fun liveCameraWithAudioRequestsBothOnlyOnce() {
  assertArrayEquals(arrayOf(Manifest.permission.CAMERA,Manifest.permission.RECORD_AUDIO), GamingCapturePermissions.required(arrayOf(PermissionRequest.RESOURCE_VIDEO_CAPTURE,PermissionRequest.RESOURCE_AUDIO_CAPTURE,PermissionRequest.RESOURCE_VIDEO_CAPTURE)))
 }
 @Test fun unrelatedOrEmptyResourcesCannotBeGranted() {
  assertNull(GamingCapturePermissions.required(emptyArray()))
  assertNull(GamingCapturePermissions.required(arrayOf("android.webkit.resource.PROTECTED_MEDIA_ID")))
 }
}
