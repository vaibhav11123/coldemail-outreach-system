/**
 * Grafana k6 smoke — run against a locally hosted studio instance only.
 *
 *   k6 run studio/prod_qual/k6/smoke.js -e BASE_URL=http://127.0.0.1:8765
 *
 * NOT RUN in CI until a dedicated load environment exists.
 * Do not point this at production provider APIs.
 */
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 3,
  duration: "30s",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<2000"],
  },
};

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8765";

export default function () {
  const health = http.get(`${BASE}/health`);
  check(health, { "health 200": (r) => r.status === 200 });
  const offer = http.get(`${BASE}/offer`);
  check(offer, { "offer loads": (r) => r.status === 200 });
  sleep(0.5);
}
