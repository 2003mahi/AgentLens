import React, { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

function OrbMesh({ status }) {
  const meshRef = useRef();
  const wireframeRef = useRef();
  const ringRef = useRef();
  const nodeRef1 = useRef();
  const nodeRef2 = useRef();
  const nodeRef3 = useRef();

  const colorConfig = {
    idle: { core: '#3b82f6', emissive: '#1d4ed8', wire: '#60a5fa', light: '#93c5fd' },
    running: { core: '#f59e0b', emissive: '#b45309', wire: '#fbbf24', light: '#fde68a' },
    success: { core: '#10b981', emissive: '#047857', wire: '#34d399', light: '#a7f3d0' },
    failed: { core: '#ef4444', emissive: '#b91c1c', wire: '#f87171', light: '#fecaca' }
  };

  const colors = colorConfig[status] || colorConfig.idle;

  useFrame((state, delta) => {
    const t = state.clock.getElapsedTime();
    const speedMultiplier = status === 'running' ? 2.2 : 0.8;

    if (meshRef.current) {
      meshRef.current.rotation.y += delta * 0.4 * speedMultiplier;
      meshRef.current.rotation.x = Math.sin(t * 0.5) * 0.15;
    }
    if (wireframeRef.current) {
      wireframeRef.current.rotation.y -= delta * 0.3 * speedMultiplier;
      wireframeRef.current.rotation.z += delta * 0.2 * speedMultiplier;
    }
    if (ringRef.current) {
      ringRef.current.rotation.z += delta * 0.5 * speedMultiplier;
      ringRef.current.rotation.x = 1.1 + Math.sin(t * 0.3) * 0.1;
    }

    // Satellite nodes orbiting
    if (nodeRef1.current) {
      nodeRef1.current.position.x = Math.cos(t * speedMultiplier) * 1.8;
      nodeRef1.current.position.z = Math.sin(t * speedMultiplier) * 1.8;
      nodeRef1.current.position.y = Math.sin(t * speedMultiplier * 1.5) * 0.4;
    }
    if (nodeRef2.current) {
      nodeRef2.current.position.x = Math.cos(t * speedMultiplier + 2.1) * 1.8;
      nodeRef2.current.position.z = Math.sin(t * speedMultiplier + 2.1) * 1.8;
      nodeRef2.current.position.y = Math.sin((t * speedMultiplier + 2.1) * 1.5) * 0.4;
    }
    if (nodeRef3.current) {
      nodeRef3.current.position.x = Math.cos(t * speedMultiplier + 4.2) * 1.8;
      nodeRef3.current.position.z = Math.sin(t * speedMultiplier + 4.2) * 1.8;
      nodeRef3.current.position.y = Math.sin((t * speedMultiplier + 4.2) * 1.5) * 0.4;
    }
  });

  return (
    <group>
      <ambientLight intensity={0.7} />
      <pointLight position={[5, 5, 5]} intensity={1.5} color={colors.light} />
      <pointLight position={[-5, -5, -3]} intensity={0.8} color="#ffffff" />

      {/* Central Solid Glowing Orb */}
      <mesh ref={meshRef}>
        <sphereGeometry args={[0.95, 32, 32]} />
        <meshStandardMaterial
          color={colors.core}
          emissive={colors.emissive}
          emissiveIntensity={status === 'running' ? 0.8 : 0.4}
          roughness={0.2}
          metalness={0.85}
        />
      </mesh>

      {/* Outer Geometric Wireframe Lattice */}
      <mesh ref={wireframeRef}>
        <icosahedronGeometry args={[1.35, 1]} />
        <meshStandardMaterial
          color={colors.wire}
          wireframe
          transparent
          opacity={0.55}
          emissive={colors.wire}
          emissiveIntensity={0.3}
        />
      </mesh>

      {/* Orbital Evaluation Ring */}
      <mesh ref={ringRef} rotation={[1.1, 0, 0]}>
        <torusGeometry args={[1.8, 0.02, 16, 64]} />
        <meshBasicMaterial color={colors.wire} transparent opacity={0.4} />
      </mesh>

      {/* Satellite Agent Nodes */}
      <mesh ref={nodeRef1}>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshBasicMaterial color={colors.light} />
      </mesh>
      <mesh ref={nodeRef2}>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshBasicMaterial color="#38bdf8" />
      </mesh>
      <mesh ref={nodeRef3}>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshBasicMaterial color="#a855f7" />
      </mesh>
    </group>
  );
}

export default function EvaluationOrb3D({ status = 'idle' }) {
  return (
    <div style={{ width: '100%', height: '100%', minHeight: '220px', position: 'relative' }}>
      <Canvas
        camera={{ position: [0, 0, 3.8], fov: 45 }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, alpha: true, powerPreference: 'low-power' }}
      >
        <OrbMesh status={status} />
      </Canvas>
    </div>
  );
}
