/**
 * ResQGrid Hyderabad Tactical Geo Projection Adapter
 *
 * Converts real WGS84 geographic coordinates (latitude, longitude) into the 2D
 * percentage coordinates ({ x, y } in [0, 100]%) used by the SVG map in EmergencyMap.jsx.
 */

/**
 * Standard Hyderabad sector bounding box calibrated against seeded landmarks:
 * - Longitude bounds: 78.32°E (Gachibowli / West) to 78.55°E (Dilsukhnagar / East)
 * - Latitude bounds: 17.34°N (Charminar / South) to 17.47°N (Secunderabad / North)
 * - Map canvas percentage viewport: 15% to 85% to provide comfortable margins
 */
export const HYDERABAD_BOUNDS = Object.freeze({
  minLat: 17.34,
  maxLat: 17.47,
  minLon: 78.32,
  maxLon: 78.55,
  minX: 18,
  maxX: 78,
  minY: 18,
  maxY: 78,
});

/**
 * Converts WGS84 latitude and longitude into 2D SVG canvas percentage coordinates.
 *
 * In screen/SVG space:
 * - X percentage increases from West (minLon) to East (maxLon).
 * - Y percentage increases from North (maxLat, top of screen) to South (minLat, bottom of screen).
 *
 * @param {number|string|null|undefined} latitude - WGS84 latitude in degrees
 * @param {number|string|null|undefined} longitude - WGS84 longitude in degrees
 * @param {object} [bounds=HYDERABAD_BOUNDS] - Custom projection boundaries
 * @returns {{ x: number, y: number, isValid: boolean }}
 */
export function projectCoordinates(latitude, longitude, bounds = HYDERABAD_BOUNDS) {
  // Check for pre-existing coordinates object
  if (
    latitude &&
    typeof latitude === 'object'
  ) {
    if (
      latitude.isValid === false ||
      latitude.isProjected === false ||
      latitude.x === null ||
      latitude.y === null ||
      typeof latitude.x !== 'number' ||
      typeof latitude.y !== 'number'
    ) {
      return {
        x: null,
        y: null,
        isValid: false,
        isProjected: false,
      };
    }
    return {
      x: clamp(latitude.x, 5, 95),
      y: clamp(latitude.y, 5, 95),
      isValid: true,
      isProjected: true,
    };
  }

  const lat = typeof latitude === 'number' ? latitude : parseFloat(latitude);
  const lon = typeof longitude === 'number' ? longitude : parseFloat(longitude);

  // Validate numeric values and geographic limits
  // Unprojectable coordinates return nulls and isProjected: false.
  // They must NEVER be placed at the map center (e.g. 50%, 50%).
  if (
    !Number.isFinite(lat) ||
    !Number.isFinite(lon) ||
    lat < -90 ||
    lat > 90 ||
    lon < -180 ||
    lon > 180
  ) {
    return {
      x: null,
      y: null,
      isValid: false,
      isProjected: false,
    };
  }

  const b = bounds || HYDERABAD_BOUNDS;

  // Linear interpolation along longitude (X-axis)
  const lonRatio = (lon - b.minLon) / (b.maxLon - b.minLon);
  const rawX = b.minX + lonRatio * (b.maxX - b.minX);

  // Inverted linear interpolation along latitude (Y-axis: North is top/low Y)
  const latRatio = (b.maxLat - lat) / (b.maxLat - b.minLat);
  const rawY = b.minY + latRatio * (b.maxY - b.minY);

  // Clamp strictly within the visible canvas boundaries [5%, 95%]
  const clampedX = clamp(rawX, 5, 95);
  const clampedY = clamp(rawY, 5, 95);

  return {
    x: Math.round(clampedX * 10) / 10,
    y: Math.round(clampedY * 10) / 10,
    isValid: true,
    isProjected: true,
  };
}

/**
 * Utility helper to clamp a numeric value between min and max bounds.
 *
 * @param {number} value
 * @param {number} min
 * @param {number} max
 * @returns {number}
 */
export function clamp(value, min, max) {
  if (!Number.isFinite(value)) return min;
  return Math.min(Math.max(value, min), max);
}

