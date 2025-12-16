import type { HTMLAttributes, ReactNode } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  hover?: boolean;
}

export function Card({ children, hover = false, className = '', ...props }: CardProps) {
  const baseStyles = 'bg-white rounded-xl shadow-sm border border-gray-200';
  const hoverStyles = hover ? 'transition-shadow duration-200 hover:shadow-md cursor-pointer' : '';

  return (
    <div className={`${baseStyles} ${hoverStyles} ${className}`} {...props}>
      {children}
    </div>
  );
}

interface CardHeaderProps {
  children: ReactNode;
  className?: string;
}

export function CardHeader({ children, className = '' }: CardHeaderProps) {
  return <div className={`px-6 py-4 border-b border-gray-200 ${className}`}>{children}</div>;
}

interface CardBodyProps {
  children: ReactNode;
  className?: string;
}

export function CardBody({ children, className = '' }: CardBodyProps) {
  return <div className={`p-6 ${className}`}>{children}</div>;
}

interface CardFooterProps {
  children: ReactNode;
  className?: string;
}

export function CardFooter({ children, className = '' }: CardFooterProps) {
  return (
    <div className={`px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-xl ${className}`}>
      {children}
    </div>
  );
}
