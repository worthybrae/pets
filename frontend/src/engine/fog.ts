/** Fog that starts past the camera's target and hides the edge of the loaded terrain. */
export function fogRange(viewDistance: number, cameraDistance: number): [number, number] {
  const loaded = viewDistance * 16
  return [cameraDistance + loaded * 0.4, cameraDistance + loaded]
}
