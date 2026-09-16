/**
 * System achievements overview presenting unlocked milestones, badges, and streak statistics.
 *
 * Author: ChaChan26 <minhharry2006@gmail.com>
 * Copyright (c) 2026 ChaChan26. All rights reserved.
 */

import React from 'react';
import { motion } from 'motion/react';
import { 
  Footprints, Shield, Droplets, ShieldCheck, Brain, Moon, 
  Sunrise, Zap, Target, Timer, Lock, Trophy, Flame, AlertCircle
} from 'lucide-react';
import { useAchievements } from '../hooks/useAchievements';

const ICON_MAP: Record<string, typeof Trophy> = {
  Footprints, Shield, Droplets, ShieldCheck, Brain, Moon, Sunrise, Zap, Target, Timer, Lock, Trophy, Flame
};

export function Achievements() {
  const { achievements, unlockedCount, totalCount, loading, error, streakDays, longestStreakDays } = useAchievements();

  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.05 }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 10 },
    show: { opacity: 1, y: 0, transition: { type: 'spring' as const, stiffness: 300, damping: 24 } }
  };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    const today = new Date();
    if (d.toDateString() === today.toDateString()) return 'Today';
    
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
    
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  };

  return (
    <div style={{ padding: '2rem', height: '100%', overflowY: 'auto' }} className="custom-scrollbar">
      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px', borderRadius: 'var(--radii-md)', background: 'color-mix(in srgb, var(--destructive) 10%, transparent)', color: 'var(--destructive)', fontSize: '0.85rem', marginBottom: '1.5rem', border: '1px solid color-mix(in srgb, var(--destructive) 25%, transparent)' }}>
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Hero Stats Section */}
      <div style={{ display: 'flex', gap: '1.25rem', marginBottom: '2.5rem', flexWrap: 'wrap' }}>
        {[
          { label: 'Unlocked', value: `${unlockedCount}/${totalCount}`, icon: Trophy, color: 'var(--primary)' },
          { label: 'Current Streak', value: `${streakDays} Days`, icon: Flame, color: 'var(--accent-1)' },
          { label: 'Longest Streak', value: `${longestStreakDays} Days`, icon: Shield, color: 'var(--accent-2)' },
        ].map((stat, i) => (
          <div key={i} style={{ 
            flex: '1 1 200px',
            background: 'var(--glass-bg, rgba(255, 255, 255, 0.03))',
            backdropFilter: 'blur(12px)',
            borderRadius: '1.25rem',
            padding: '1.25rem',
            border: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            gap: '1rem'
          }}>
            <div style={{ 
              width: 48, height: 48, borderRadius: '50%', 
              background: `color-mix(in srgb, ${stat.color} 15%, transparent)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <stat.icon size={24} style={{ color: stat.color }} />
            </div>
            <div>
              <div style={{ color: 'var(--muted-foreground)', fontSize: '0.85rem', fontWeight: 500 }}>{stat.label}</div>
              <motion.div 
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--foreground)' }}
              >
                {loading ? '-' : stat.value}
              </motion.div>
            </div>
          </div>
        ))}
      </div>

      {/* Badge Grid */}
      {achievements.length === 0 && !loading ? (
        <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--muted-foreground)' }}>
          <Trophy size={48} style={{ margin: '0 auto', marginBottom: '1rem', opacity: 0.5 }} />
          <p style={{ fontSize: '1.1rem' }}>No achievements available.</p>
        </div>
      ) : (
        <motion.div 
          variants={containerVariants}
          initial="hidden"
          animate="show"
          style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: '1.25rem'
          }}
        >
          {achievements.map(ach => {
            const unlocked = ach.awarded_at !== null;
            const Icon = unlocked ? ICON_MAP[ach.icon] || Trophy : Lock;

            return (
              <motion.div
                key={ach.id}
                variants={itemVariants}
                whileHover={unlocked ? { scale: 1.02, transition: { duration: 0.2 } } : {}}
                style={{
                  background: 'var(--card)',
                  border: '1px solid var(--border)',
                  borderRadius: '1.25rem',
                  padding: '1.25rem',
                  boxShadow: 'var(--shadow-md, 0 4px 6px rgba(0,0,0,0.05))',
                  position: 'relative',
                  overflow: 'hidden',
                  opacity: unlocked ? 1 : 0.5,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.75rem'
                }}
              >
                {/* Accent Bar */}
                <div style={{
                  position: 'absolute',
                  left: 0, top: 0, bottom: 0,
                  width: '4px',
                  background: ach.color,
                  filter: unlocked ? 'none' : 'grayscale(100%)'
                }} />

                {/* Shimmer Effect */}
                {unlocked && (
                  <div style={{
                    position: 'absolute',
                    top: 0, left: 0, right: 0, bottom: 0,
                    background: 'linear-gradient(135deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.03) 50%, rgba(255,255,255,0) 100%)',
                    backgroundSize: '200% 200%',
                    pointerEvents: 'none'
                  }} className="achievement-shimmer" />
                )}

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', paddingLeft: '0.25rem' }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: '50%',
                    background: `color-mix(in srgb, ${unlocked ? ach.color : 'var(--muted-foreground)'} 15%, transparent)`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    <Icon size={24} style={{ color: unlocked ? ach.color : 'var(--muted-foreground)' }} />
                  </div>
                  <div style={{ fontWeight: 600, fontSize: '1.05rem', color: 'var(--foreground)' }}>
                    {ach.name}
                  </div>
                </div>

                <div style={{ 
                  color: 'var(--muted-foreground)', 
                  fontSize: '0.85rem', 
                  lineHeight: 1.4,
                  paddingLeft: '0.25rem',
                  flex: 1,
                  filter: unlocked ? 'none' : 'blur(2px)'
                }}>
                  {unlocked ? ach.description : '???'}
                </div>

                {unlocked && ach.awarded_at && (
                  <div style={{ 
                    fontFamily: "'DM Mono', monospace", 
                    fontSize: '0.7rem', 
                    color: 'var(--muted-foreground)',
                    marginTop: 'auto',
                    paddingLeft: '0.25rem'
                  }}>
                    Awarded {formatDate(ach.awarded_at)}
                  </div>
                )}
              </motion.div>
            );
          })}
        </motion.div>
      )}

      {/* Add a global style for the shimmer animation */}
      <style>{`
        .achievement-shimmer:hover {
          animation: shimmer 1.5s ease infinite;
        }
        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </div>
  );
}
