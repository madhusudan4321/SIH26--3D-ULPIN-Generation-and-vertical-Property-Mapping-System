/**
 * ValidationPanel Component
 *
 * Displays topology validation check results for a property.
 * Shows structured PASS / WARNING / ERROR per check rule.
 */

const STATUS_ICONS = {
  PASS: "✅",
  WARNING: "⚠️",
  ERROR: "❌",
};

const STATUS_CLASSES = {
  PASS: "validation-pass",
  WARNING: "validation-warning",
  ERROR: "validation-error",
};

export default function ValidationPanel({ validationResult }) {
  if (!validationResult) return null;

  const { overall_status, checks } = validationResult;
  const passCount = checks.filter((c) => c.status === "PASS").length;

  return (
    <div className="validation-panel">
      <div className={`validation-overall ${STATUS_CLASSES[overall_status]}`}>
        <span className="validation-overall-icon">
          {STATUS_ICONS[overall_status]}
        </span>
        <span className="validation-overall-text">
          {overall_status} ({passCount}/{checks.length} checks)
        </span>
      </div>

      <div className="validation-checks">
        {checks.map((check, idx) => (
          <div key={idx} className={`validation-check ${STATUS_CLASSES[check.status]}`}>
            <span className="validation-check-icon">
              {STATUS_ICONS[check.status]}
            </span>
            <div className="validation-check-content">
              <span className="validation-check-name">{check.name}</span>
              <span className="validation-check-detail">{check.detail}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
