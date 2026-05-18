"use client";

import { motion } from "framer-motion";
import {
  Shield,
  Globe,
  Building2,
  Server,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";

interface RiskAnalysisPanelProps {
  riskAnalysis: string;
  brokerRequirements: string;
  propFirmSafety: string;
  slippageSensitivity: string;
  brokerDependency: string;
  survivability: string;
  accountLifetime: string;
  overfittingProbability?: number;
  overfittingIndicators: string[];
}

export default function RiskAnalysisPanel({
  riskAnalysis,
  brokerRequirements,
  propFirmSafety,
  slippageSensitivity,
  brokerDependency,
  survivability,
  accountLifetime,
  overfittingProbability,
  overfittingIndicators,
}: RiskAnalysisPanelProps) {
  const sensColor =
    slippageSensitivity === "Critical" || slippageSensitivity === "High"
      ? "text-red-400"
      : slippageSensitivity === "Medium"
      ? "text-yellow-400"
      : "text-green-400";

  const depColor =
    brokerDependency === "High"
      ? "text-red-400"
      : brokerDependency === "Medium"
      ? "text-yellow-400"
      : "text-green-400";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
      className="space-y-4"
    >
      {/* Risk Analysis */}
      {riskAnalysis && (
        <div className="glass rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="w-5 h-5 text-red-400" />
            <h3 className="text-sm font-semibold text-foreground">Risk Analysis</h3>
          </div>
          <p className="text-sm text-foreground/70 leading-relaxed">{riskAnalysis}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Broker Requirements */}
        {brokerRequirements && (
          <div className="glass rounded-xl p-5">
            <div className="flex items-center gap-2 mb-3">
              <Globe className="w-5 h-5 text-blue-400" />
              <h3 className="text-sm font-semibold text-foreground">
                Broker Requirements
              </h3>
            </div>
            <p className="text-sm text-foreground/70 leading-relaxed">
              {brokerRequirements}
            </p>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-muted/30">
                <p className="text-xs text-muted-foreground">Slippage Sensitivity</p>
                <p className={`text-sm font-semibold ${sensColor}`}>
                  {slippageSensitivity || "N/A"}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-muted/30">
                <p className="text-xs text-muted-foreground">Broker Dependency</p>
                <p className={`text-sm font-semibold ${depColor}`}>
                  {brokerDependency || "N/A"}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Prop Firm Safety */}
        {propFirmSafety && (
          <div className="glass rounded-xl p-5">
            <div className="flex items-center gap-2 mb-3">
              <Building2 className="w-5 h-5 text-purple-400" />
              <h3 className="text-sm font-semibold text-foreground">
                Prop Firm Safety
              </h3>
            </div>
            <p className="text-sm text-foreground/70 leading-relaxed">
              {propFirmSafety}
            </p>
          </div>
        )}

        {/* Overfitting */}
        {overfittingProbability !== undefined && overfittingProbability !== null && (
          <div className="glass rounded-xl p-5">
            <div className="flex items-center gap-2 mb-3">
              <Server className="w-5 h-5 text-orange-400" />
              <h3 className="text-sm font-semibold text-foreground">
                Overfitting Risk
              </h3>
            </div>
            <div className="flex items-center gap-4 mb-3">
              <div className="text-3xl font-bold" style={{
                color: overfittingProbability > 60 ? "#ef4444" : overfittingProbability > 30 ? "#f59e0b" : "#22c55e"
              }}>
                {overfittingProbability}%
              </div>
              <div className="flex-1">
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{
                      backgroundColor: overfittingProbability > 60 ? "#ef4444" : overfittingProbability > 30 ? "#f59e0b" : "#22c55e"
                    }}
                    initial={{ width: 0 }}
                    animate={{ width: `${overfittingProbability}%` }}
                    transition={{ duration: 1 }}
                  />
                </div>
              </div>
            </div>
            {overfittingIndicators.length > 0 && (
              <ul className="space-y-1.5">
                {overfittingIndicators.map((ind, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-foreground/60">
                    <AlertTriangle className="w-3 h-3 text-orange-400 mt-0.5 shrink-0" />
                    {ind}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Survivability */}
        {survivability && (
          <div className="glass rounded-xl p-5">
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle2 className="w-5 h-5 text-green-400" />
              <h3 className="text-sm font-semibold text-foreground">
                Long-Term Survivability
              </h3>
            </div>
            <p className="text-sm text-foreground/70 leading-relaxed mb-3">
              {survivability}
            </p>
            {accountLifetime && (
              <div className="p-3 rounded-lg bg-muted/30">
                <p className="text-xs text-muted-foreground">Estimated Account Lifetime</p>
                <p className="text-sm font-semibold text-foreground">{accountLifetime}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}
