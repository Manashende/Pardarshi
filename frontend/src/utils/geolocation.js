// Wraps the browser's callback-based geolocation API in a Promise so it
// can be awaited alongside the other async steps in a share submission.
export function getCurrentLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Location access is not available in this browser.'));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
      },
      (err) => {
        reject(new Error(
          err.code === err.PERMISSION_DENIED
            ? 'Location permission is required to submit a share. Please allow location access and try again.'
            : `Could not determine location: ${err.message}`
        ));
      },
      // enableHighAccuracy forces GPS-grade lookup, which on a device with
      // no GPS hardware (most laptops) falls back to slow network-based
      // positioning and can take 8-10+ seconds. Network-accuracy location
      // is more than precise enough for the geofence check this feeds into,
      // and resolves in a fraction of the time.
      { enableHighAccuracy: false, timeout: 8000 }
    );
  });
}