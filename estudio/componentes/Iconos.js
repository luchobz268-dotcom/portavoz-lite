// Íconos dibujados a mano, todos con el mismo trazo. El de la marca es el de la landing (video parado).

export function IconoMarca() {
  return (
    <span className="monograma" aria-hidden="true">
      <svg viewBox="0 0 16 28" width="12" height="21">
        <rect x="0.75" y="0.75" width="14.5" height="26.5" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <rect x="3" y="16" width="5" height="1.8" fill="#E5FFF4" />
        <rect x="9" y="16" width="4" height="1.8" fill="#4FBFD3" />
        <rect x="4.5" y="19.6" width="7" height="1.8" fill="#E5FFF4" />
      </svg>
    </span>
  );
}

const trazo = { fill: "none", stroke: "currentColor", strokeWidth: 1.75, strokeLinecap: "round", strokeLinejoin: "round" };

export function IconoAviso({ tam = 20 }) {
  return (
    <svg viewBox="0 0 20 20" width={tam} height={tam} aria-hidden="true" {...trazo}>
      <path d="M10 2.8 18.2 17H1.8L10 2.8Z" />
      <path d="M10 8v4" />
      <circle cx="10" cy="14.6" r="0.4" fill="currentColor" />
    </svg>
  );
}

export function IconoInfo({ tam = 20 }) {
  return (
    <svg viewBox="0 0 20 20" width={tam} height={tam} aria-hidden="true" {...trazo}>
      <circle cx="10" cy="10" r="8" />
      <path d="M10 9v5" />
      <circle cx="10" cy="6.2" r="0.4" fill="currentColor" />
    </svg>
  );
}

export function IconoCheck({ tam = 12 }) {
  return (
    <svg viewBox="0 0 12 12" width={tam} height={tam} aria-hidden="true" {...trazo} strokeWidth={2}>
      <path d="M2.5 6.2 5 8.5l4.5-5" />
    </svg>
  );
}

export function IconoReloj({ tam = 14 }) {
  return (
    <svg viewBox="0 0 20 20" width={tam} height={tam} aria-hidden="true" {...trazo}>
      <circle cx="10" cy="10" r="8" />
      <path d="M10 5.5V10l3 2" />
    </svg>
  );
}

export function IconoFlecha({ tam = 16 }) {
  return (
    <svg viewBox="0 0 16 16" width={tam} height={tam} aria-hidden="true" {...trazo}>
      <path d="M5 11 11 5M6 5h5v5" />
    </svg>
  );
}

export function IconoEspera({ tam = 14 }) {
  return (
    <svg viewBox="0 0 20 20" width={tam} height={tam} aria-hidden="true" {...trazo}>
      <circle cx="10" cy="10" r="6" strokeDasharray="2.4 2.6" />
    </svg>
  );
}

export function IconoBajar({ tam = 18 }) {
  return (
    <svg viewBox="0 0 20 20" width={tam} height={tam} aria-hidden="true" {...trazo}>
      <path d="M10 3v9.5" />
      <path d="m6 8.8 4 4 4-4" />
      <path d="M4 16.5h12" />
    </svg>
  );
}

export function IconoCopiar({ tam = 16 }) {
  return (
    <svg viewBox="0 0 20 20" width={tam} height={tam} aria-hidden="true" {...trazo}>
      <rect x="7" y="6.5" width="9" height="11" rx="1.8" />
      <path d="M13 3.5H5.8A1.8 1.8 0 0 0 4 5.3V14" />
    </svg>
  );
}

export function IconoOtro({ tam = 16 }) {
  return (
    <svg viewBox="0 0 20 20" width={tam} height={tam} aria-hidden="true" {...trazo}>
      <path d="M16 10a6 6 0 1 1-1.8-4.3" />
      <path d="M16 3.6v3.3h-3.3" />
    </svg>
  );
}
