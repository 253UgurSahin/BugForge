/* Tidewatch, level 5 (as level 4): the tide the page already shows, as numbers for the scripts.
   Reads the week's curve (.tide__curve, Tue 00:00 to Mon 24:00, 10 units an hour, 100 units a metre
   from 600 = chart datum) and the safe windows (.tide__window, in percent of the week), so the hero
   and the story use the very same tide as the chart and the table. No request, no model of its own. */

const HOURS = 168;
const DAYS = ["Tue 10", "Wed 11", "Thu 12", "Fri 13", "Sat 14", "Sun 15", "Mon 16"];
export const NOW = 9 + 40 / 60;        // the page's "Now 09:40", Tuesday

export function readTide(doc = document) {
  const path = doc.querySelector(".tide__curve");
  const points = [];
  const numbers = (path ? path.getAttribute("d") || "" : "").match(/-?\d+(?:\.\d+)?/g) || [];
  for (let i = 0; i + 1 < numbers.length; i += 2) points.push([Number(numbers[i]), Number(numbers[i + 1])]);
  const windows = [...doc.querySelectorAll(".tide__window")].map((el) => {
    const x = parseFloat(el.style.getPropertyValue("--x")), w = parseFloat(el.style.getPropertyValue("--w"));
    return [(x / 100) * HOURS, ((x + w) / 100) * HOURS];
  }).filter(([a, b]) => Number.isFinite(a) && Number.isFinite(b));
  const heights = points.map(([, y]) => (600 - y) / 100);
  const low = Math.min(...heights, 0.5), high = Math.max(...heights, 5);

  // metres above chart datum at an hour of the week (0 = Tue 00:00), straight between the points
  function height(hour) {
    if (!points.length) return 2.5;
    const x = Math.min(Math.max(hour, 0), HOURS) * 10;
    let i = points.findIndex(([px]) => px >= x);
    if (i <= 0) return heights[Math.max(i, 0)];
    const [x0] = points[i - 1], [x1] = points[i];
    const t = x1 === x0 ? 0 : (x - x0) / (x1 - x0);
    return heights[i - 1] + (heights[i] - heights[i - 1]) * t;
  }
  return {
    hours: HOURS,
    height,
    rising: (hour) => height(hour + 0.25) > height(hour),
    level: (hour) => (height(hour) - low) / (high - low),          // 0 at the lowest water of the week, 1 at the highest
    safe: (hour) => windows.some(([a, b]) => hour >= a && hour <= b),
    windowAt: (hour) => windows.findIndex(([a, b]) => hour >= a && hour <= b),
    day: (hour) => DAYS[Math.min(DAYS.length - 1, Math.max(0, Math.floor(hour / 24)))],
    clock: (hour) => {
      const minutes = Math.round((((hour % 24) + 24) % 24) * 60) % 1440;
      return String(Math.floor(minutes / 60)).padStart(2, "0") + ":" + String(minutes % 60).padStart(2, "0");
    },
  };
}
