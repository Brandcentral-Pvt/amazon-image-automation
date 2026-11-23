"use client";

import { type HTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface AvatarProps extends HTMLAttributes<HTMLDivElement> {
  src?: string;
  alt?: string;
  name?: string;
  size?: "xs" | "sm" | "md" | "lg" | "xl";
  shape?: "circle" | "square";
  fallback?: ReactNode;
}

export function Avatar({
  className,
  src,
  alt,
  name,
  size = "md",
  shape = "circle",
  fallback,
  ...props
}: AvatarProps) {
  const sizeStyles = {
    xs: "avatar-xs",
    sm: "avatar-sm",
    md: "avatar-md",
    lg: "avatar-lg",
    xl: "avatar-xl",
  };
  const shapeStyles = {
    circle: "rounded-full",
    square: "rounded-lg",
  };

  const initials = name
    ? name
        .split(" ")
        .map((n) => n[0])
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "?";

  const [imgError, setImgError] = useState(false);

  return (
    <div
      ref={props.ref}
      className={cn("avatar", sizeStyles[size], shapeStyles[shape], className)}
      {...props}
    >
      {src && !imgError ? (
        <img
          src={src}
          alt={alt || name || ""}
          className="w-full h-full object-cover"
          onError={() => setImgError(true)}
        />
      ) : fallback ? (
        fallback
      ) : (
        <span className="font-medium text-center leading-none">{initials}</span>
      )}
    </div>
  );
}

import { useState } from "react";

Avatar.displayName = "Avatar";

export interface AvatarGroupProps {
  avatars: Array<{ src?: string; name: string; alt?: string }>;
  max?: number;
  size?: "xs" | "sm" | "md" | "lg" | "xl";
  className?: string;
}

export function AvatarGroup({ avatars, max = 5, size = "md", className }: AvatarGroupProps) {
  const visibleAvatars = avatars.slice(0, max);
  const remainingCount = avatars.length - max;

  return (
    <div className={cn("flex -space-x-2", className)}>
      {visibleAvatars.map((avatar, index) => (
        <Avatar
          key={index}
          src={avatar.src}
          name={avatar.name}
          alt={avatar.alt}
          size={size}
          className={cn("border-2 border-white dark:border-surface-900", index === 0 && "z-10")}
        />
      ))}
      {remainingCount > 0 && (
        <Avatar
          size={size}
          name={`+${remainingCount}`}
          className="bg-surface-100 text-surface-600 border-2 border-white dark:border-surface-900"
        />
      )}
    </div>
  );
}

export { Avatar, AvatarGroup };