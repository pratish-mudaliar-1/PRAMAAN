import React from 'react';

// Maps any status string → chip CSS class + icon character
const STATUS_MAP: Record<string, { cls: string; icon: string; label: string }> = {
  GREEN:                { cls: 'chip-green',       icon: '●', label: 'Green'                },
  AMBER:                { cls: 'chip-amber',       icon: '◆', label: 'Amber'                },
  RED:                  { cls: 'chip-red',         icon: '■', label: 'Red'                  },
  'NO-DATA':            { cls: 'chip-nodata',      icon: '⬡', label: 'No data'              },
  PENDING:              { cls: 'chip-pending',     icon: '○', label: 'Pending'              },
  UNCERTAIN:            { cls: 'chip-uncertain',   icon: '◌', label: 'Uncertain'            },
  EVIDENCE_COMPROMISED: { cls: 'chip-compromised', icon: '⚠', label: 'Evidence compromised' },
  SAME_VIEW:            { cls: 'chip-same-view',   icon: '●', label: 'Same view'            },
  VIEW_DRIFTED:         { cls: 'chip-amber',       icon: '↕', label: 'View drifted'         },
  VIEW_MISMATCH:        { cls: 'chip-mismatch',    icon: '≠', label: 'View mismatch'        },
  SUSPECTED_SWAP:       { cls: 'chip-swap',        icon: '↔', label: 'Suspected swap'       },
  SWAP_CONFIRMED:       { cls: 'chip-escalated',   icon: '✕', label: 'Swap confirmed'       },
  REBASELINE_PENDING:   { cls: 'chip-rebaseline',  icon: '↻', label: 'Re-baseline pending'  },
  CLEAR:                { cls: 'chip-clear',       icon: '●', label: 'Clear'                },
  WATCH:                { cls: 'chip-watch',       icon: '◎', label: 'Watch'                },
  SUSPECTED_GHOST:      { cls: 'chip-ghost',       icon: '👻', label: 'Suspected ghost'     },
  ESCALATED:            { cls: 'chip-escalated',   icon: '⬆', label: 'Escalated'            },
  PRESENT:              { cls: 'chip-green',       icon: '✓', label: 'Present'              },
  ABSENT:               { cls: 'chip-red',         icon: '✗', label: 'Absent'               },
  FEED_BLOCKED:         { cls: 'chip-nodata',      icon: '⬛', label: 'Feed blocked'         },
  FEED_FROZEN:          { cls: 'chip-amber',       icon: '❄', label: 'Feed frozen'          },
  HIGH:                 { cls: 'chip-high',        icon: '▲', label: 'High'                 },
  MEDIUM:               { cls: 'chip-medium',      icon: '►', label: 'Medium'               },
  LOW:                  { cls: 'chip-low',         icon: '▼', label: 'Low'                  },
  OPEN:                 { cls: 'chip-red',         icon: '●', label: 'Open'                 },
  TC_RESPONDED:         { cls: 'chip-amber',       icon: '↩', label: 'TC responded'         },
  UNDER_REVIEW:         { cls: 'chip-rebaseline',  icon: '🔍', label: 'Under review'        },
  CLOSED:               { cls: 'chip-clear',       icon: '✓', label: 'Closed'               },
  ONLINE:               { cls: 'chip-green',       icon: '●', label: 'Online'               },
  OFFLINE:              { cls: 'chip-red',         icon: '●', label: 'Offline'              },
  DEGRADED:             { cls: 'chip-amber',       icon: '◆', label: 'Degraded'             },
};

interface StatusChipProps {
  status: string;
  /** Override display label */
  label?: string;
  size?: 'xs' | 'sm';
  className?: string;
}

export function StatusChip({ status, label, size, className }: StatusChipProps) {
  const def = STATUS_MAP[status] ?? { cls: 'chip-nodata', icon: '?', label: status };
  const sizeStyle = size === 'xs'
    ? { fontSize: '0.65rem', padding: '1px 5px' }
    : {};

  return (
    <span className={`chip ${def.cls} ${className ?? ''}`} style={sizeStyle} title={def.label}>
      <span aria-hidden="true">{def.icon}</span>
      <span>{label ?? def.label}</span>
    </span>
  );
}

// Named export alias used by ComponentGallery
export const STATUS_CONFIG = STATUS_MAP;
