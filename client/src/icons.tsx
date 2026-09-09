type IconProps = { size?: number };

const Icon = ({ children, size = 20 }: IconProps & { children: React.ReactNode }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {children}
  </svg>
);

export const MicIcon = (props: IconProps) => <Icon {...props}><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5M8 22h8"/></Icon>;
export const MutedIcon = (props: IconProps) => <Icon {...props}><path d="m2 2 20 20M9 9v1a3 3 0 0 0 5.1 2.1M15 9.3V5a3 3 0 0 0-5.6-1.5M5 10a7 7 0 0 0 11.8 5.1M19 10a7 7 0 0 1-.4 2.3M12 17v5M8 22h8"/></Icon>;
export const FileIcon = (props: IconProps) => <Icon {...props}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h6"/></Icon>;
export const ClockIcon = (props: IconProps) => <Icon {...props}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></Icon>;
export const CheckIcon = (props: IconProps) => <Icon {...props}><path d="m5 12 4 4L19 6"/></Icon>;
export const ArrowIcon = (props: IconProps) => <Icon {...props}><path d="M5 12h14M14 7l5 5-5 5"/></Icon>;
export const ShieldIcon = (props: IconProps) => <Icon {...props}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></Icon>;
export const SparkIcon = (props: IconProps) => <Icon {...props}><path d="m12 3-1.2 3.8A6 6 0 0 1 7 10.6L3 12l4 1.4a6 6 0 0 1 3.8 3.8L12 21l1.2-3.8a6 6 0 0 1 3.8-3.8l4-1.4-4-1.4a6 6 0 0 1-3.8-3.8z"/></Icon>;
