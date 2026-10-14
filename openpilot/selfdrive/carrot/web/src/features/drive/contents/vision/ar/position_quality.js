/* Phase 7C — TMap geo anchor에 대한 독립 위치 품질 gate.
 *
 * 실제 anchor 기준은 계속 carrotNavi.vehicle이다. gpsLocationExternal 좌표로 화면 위치를
 * 계산하거나 두 GPS를 평균내지 않는다. Comma GPS는 두 소스가 심하게 어긋난 경우 먼 geo
 * anchor를 거부하는 교차검증용이며, 거부 시 근거리 model-path anchor로 강등한다.
 */

import { arText } from "./i18n.js";
import { enuOffset } from "./geo.js";
import { AR_POSITION_QUALITY } from "./tokens.js";

function finite(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function validCoordinate(latitude, longitude) {
  const lat = finite(latitude);
  const lon = finite(longitude);
  return lat !== null && lon !== null
    && lat >= -90 && lat <= 90
    && lon >= -180 && lon <= 180;
}

function validRoutePolyline(polyline) {
  if (!Array.isArray(polyline)) return false;
  let validPoints = 0;
  for (const point of polyline) {
    if (validCoordinate(point?.latitude, point?.longitude)) validPoints += 1;
    if (validPoints >= 2) return true;
  }
  return false;
}

function receiptAgeMs(nowMs, receipts, service) {
  const now = finite(nowMs);
  const received = finite(receipts?.[service]);
  if (now === null || received === null || now < received) return null;
  return now - received;
}

export function headingDifferenceDeg(a, b) {
  const left = finite(a);
  const right = finite(b);
  if (left === null || right === null) return null;
  const delta = Math.abs(((left - right + 540) % 360) - 180);
  return delta;
}

export function evaluateGeoPositionQuality(input = {}, limits = AR_POSITION_QUALITY) {
  const vehicle = input.naviVehicle;
  const gps = input.gpsLocationExternal;
  const reasons = [];
  const routeReasons = [];

  if (input.naviUsable !== true) {
    reasons.push(arText("pq_navi_pos_source", "Navi 위치 source 비활성"));
    routeReasons.push(arText("pq_navi_route_source", "Navi 경로 source 비활성"));
  }
  const naviCoordinateValid = vehicle?.present !== false
    && validCoordinate(vehicle?.latitude, vehicle?.longitude)
    && finite(vehicle?.headingDeg) !== null;
  if (!naviCoordinateValid) {
    reasons.push(arText("pq_tmap_missing", "TMap vehicle 좌표/방향 없음"));
    routeReasons.push(arText("pq_tmap_missing", "TMap vehicle 좌표/방향 없음"));
  }
  const routePolylineValid = validRoutePolyline(input.naviRoutePolyline);
  if (!routePolylineValid) routeReasons.push(arText("pq_tmap_route", "TMap route polyline 없음"));
  const canUseRoute = routeReasons.length === 0;

  const replayClock = input.clockDomain === "replay-media";
  const gpsAgeMs = replayClock && gps ? 0 : receiptAgeMs(
    input.nowMs,
    input.receivedAtMonotonic,
    "gpsLocationExternal",
  );
  if (gpsAgeMs === null) reasons.push(arText("pq_gps_ts", "Comma GPS 수신시각 없음"));
  else if (gpsAgeMs > limits.maxGpsAgeMs) reasons.push(`Comma GPS age ${gpsAgeMs.toFixed(0)}ms`);

  const gpsCoordinateValid = gps?.hasFix === true
    && validCoordinate(gps?.latitude, gps?.longitude);
  if (!gpsCoordinateValid) reasons.push(arText("pq_gps_fix", "Comma GPS fix/좌표 없음"));

  const horizontalAccuracyM = finite(gps?.horizontalAccuracy);
  if (horizontalAccuracyM === null || horizontalAccuracyM < 0) {
    reasons.push(arText("pq_gps_hacc", "Comma GPS 수평 정확도 없음"));
  } else if (horizontalAccuracyM > limits.maxHorizontalAccuracyM) {
    reasons.push(arText("pq_gps_herr", "Comma GPS 수평 오차 {v}m", { v: horizontalAccuracyM.toFixed(1) }));
  }

  let separationM = null;
  if (naviCoordinateValid && gpsCoordinateValid) {
    const offset = enuOffset(
      vehicle.latitude,
      vehicle.longitude,
      gps.latitude,
      gps.longitude,
    );
    separationM = offset ? Math.hypot(offset.east, offset.north) : null;
    const separationLimitM = Math.max(
      limits.maxPositionSeparationM,
      Math.max(0, horizontalAccuracyM ?? 0) * limits.separationAccuracyMultiplier,
    );
    if (separationM === null || separationM > separationLimitM) {
      reasons.push(arText("pq_pos_mismatch", "TMap/Comma 위치 불일치 {v}m", { v: separationM?.toFixed(1) ?? "n/a" }));
    }
  }

  const gpsSpeedMps = finite(gps?.speed);
  const shouldCheckBearing = gpsSpeedMps !== null
    && gpsSpeedMps >= limits.minBearingCheckSpeedMps;
  const bearingAccuracyDeg = finite(gps?.bearingAccuracyDeg);
  let headingDisagreementDeg = null;
  if (shouldCheckBearing) {
    if (bearingAccuracyDeg === null || bearingAccuracyDeg < 0
        || bearingAccuracyDeg > limits.maxBearingAccuracyDeg) {
      reasons.push(arText("pq_heading_acc", "Comma GPS 진행방향 정확도 부족"));
    } else {
      headingDisagreementDeg = headingDifferenceDeg(vehicle?.headingDeg, gps?.bearingDeg);
      if (headingDisagreementDeg === null
          || headingDisagreementDeg > limits.maxHeadingDisagreementDeg) {
        reasons.push(arText("pq_heading_mismatch", "TMap/Comma 방향 불일치 {v}°", { v: headingDisagreementDeg?.toFixed(1) ?? "n/a" }));
      }
    }
  }

  // These are observation covariances, not a request to average the sources.
  // TMap remains the map-aligned observation; Comma GPS accuracy and the
  // measured cross-source separation determine how strongly it may correct
  // the local world pose.
  const positionSigmaM = horizontalAccuracyM === null || separationM === null
    ? null
    : Math.hypot(horizontalAccuracyM, separationM * 0.5);
  const headingSigmaDeg = shouldCheckBearing
    && bearingAccuracyDeg !== null
    && headingDisagreementDeg !== null
    ? Math.hypot(bearingAccuracyDeg, headingDisagreementDeg * 0.5)
    : null;

  return Object.freeze({
    canUseGeo: reasons.length === 0,
    canUseRoute,
    fallback: reasons.length ? (canUseRoute ? "navi-route" : "model-path") : null,
    gpsAgeMs,
    horizontalAccuracyM,
    separationM,
    bearingAccuracyDeg,
    headingDisagreementDeg,
    positionSigmaM,
    headingSigmaDeg,
    reasons: Object.freeze(reasons),
    routeReasons: Object.freeze(routeReasons),
  });
}
