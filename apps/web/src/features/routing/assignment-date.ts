/** Match the API's current UTC calendar-day assignment boundary. */
export function utcAssignmentDate(value = new Date()) {
  return value.toISOString().slice(0, 10);
}
