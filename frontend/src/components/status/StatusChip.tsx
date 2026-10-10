import React from 'react';

// Maps any status string → chip CSS class + icon character
// Status values match backend enum vocabulary exactly.
const STATUS_MAP: Record<string, { cls: string; icon: string; label: string }> = {
  // ── attendance_status ─────────────────────────────────────────────────────
  GREEN:             { cls: 'chip-green',     icon: '●', label: 'Green'            },
  AMBER:             { cls: 'chip-amber',     icon: '◆', label: 'Amber'            },
  RED:               { cls: 'chip-red',       icon: '■', label: 'Red'              },
  NO_DATA:           { cls: 'chip-nodata',    icon: '⬡', label: 'No data'          },
  PENDING:           { cls: 'chip-pending',   icon: '○', label: 'Pending'          },

  // ── camera_integrity_state ────────────────────────────────────────────────
  STABLE:            { cls: 'chip-same-view', icon: '●', label: 'Stable'           },
  DRIFT_SUSPECTED:   { cls: 'chip-amber',     icon: '↕', label: 'Drift suspected'  },
  SWAP_SUSPECTED:    { cls: 'chip-swap',      icon: '↔', label: 'Swap suspected'   },
  SWAP_CONFIRMED:    { cls: 'chip-escalated', icon: '✕', label: 'Swap confirmed'   },
  MOVED_CONFIRMED:   { cls: 'chip-escalated', icon: '➤', label: 'Moved confirmed'  },
  REBASELINED:       { cls: 'chip-rebaseline',icon: '↻', label: 'Rebaselined'      },
  RESOLVED:          { cls: 'chip-clear',     icon: '✓', label: 'Resolved'         },

  // ── ghost_assessment_state ────────────────────────────────────────────────
  NORMAL:            { cls: 'chip-clear',     icon: '●', label: 'Normal'           },
  WATCH:             { cls: 'chip-watch',     icon: '◎', label: 'Watch'            },
  SUSPECTED_GHOST:   { cls: 'chip-ghost',     icon: '👻', label: 'Suspected ghost' },
  ESCALATED:         { cls: 'chip-escalated', icon: '⬆', label: 'Escalated'        },

  // ── flag_status ───────────────────────────────────────────────────────────
  OPEN:              { cls: 'chip-red',       icon: '●', label: 'Open'             },
  UNDER_REVIEW:      { cls: 'chip-rebaseline',icon: '🔍', label: 'Under review'   },
  CLOSED_CONFIRMED:  { cls: 'chip-clear',     icon: '✓', label: 'Closed confirmed' },
  CLOSED_DISMISSED:  { cls: 'chip-nodata',    icon: '–', label: 'Closed dismissed' },

  // ── case_status (TC_RESPONDED is a case status, not flag status) ──────────
  TC_RESPONDED:      { cls: 'chip-amber',     icon: '↩', label: 'TC responded'    },

  // ── severity ──────────────────────────────────────────────────────────────
  HIGH:              { cls: 'chip-high',      icon: '▲', label: 'High'             },
  MEDIUM:            { cls: 'chip-medium',    icon: '►', label: 'Medium'           },
  LOW:               { cls: 'chip-low',       icon: '▼', label: 'Low'              },

  // ── item status ───────────────────────────────────────────────────────────
  PRESENT:           { cls: 'chip-green',     icon: '✓', label: 'Present'          },
  ABSENT:            { cls: 'chip-red',       icon: '✗', label: 'Absent'           },

  // ── device_status (backend) ───────────────────────────────────────────────
  ACTIVE:            { cls: 'chip-green',     icon: '●', label: 'Active'           },
  OFFLINE:           { cls: 'chip-red',       icon: '●', label: 'Offline'          },
  SUSPENDED:         { cls: 'chip-amber',     icon: '◆', label: 'Suspended'        },
  REVOKED:           { cls: 'chip-compromised',icon: '✕', label: 'Revoked'         },
  // PENDING already defined above (shared with attendance_status)
};

interface StatusChipProps {
  status: string;
  /** Override display label */
  label?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

export function StatusChip({ status, label, size, showLabel = true, className }: StatusChipProps) {
  const def = STATUS_MAP[status] ?? { cls: 'chip-nodata', icon: '?', label: status };
  const sizeStyle = size === 'xs'
    ? { fontSize: '0.65rem', padding: '1px 5px' }
    : size === 'lg'
    ? { fontSize: '0.85rem', padding: '4px 10px' }
    : size === 'md'
    ? { fontSize: '0.75rem', padding: '3px 8px' }
    : {};

  return (
    <span className={`chip ${def.cls} ${className ?? ''}`} style={sizeStyle} title={def.label}>
      <span aria-hidden="true">{def.icon}</span>
      {showLabel && <span>{label ?? def.label}</span>}
    </span>
  );
}

// Named export alias used by ComponentGallery
export const STATUS_CONFIG = STATUS_MAP;
