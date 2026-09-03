import {
  Badge,
  Body1Strong,
  Button,
  Dropdown,
  Field,
  Input,
  Option,
  Tab,
  TabList,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Title2,
  type SelectTabData,
} from "@fluentui/react-components";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError } from "../api/client";
import { useAppServices } from "../AppContext";
import FeatureGate from "../components/FeatureGate";
import type { AttendanceStatus, LeaveType, StaffUser } from "../types";

const ATTENDANCE_STATUSES: { value: AttendanceStatus; label: string }[] = [
  { value: "present", label: "Present" },
  { value: "absent", label: "Absent" },
  { value: "half_day", label: "Half day" },
  { value: "on_leave", label: "On leave" },
];

const LEAVE_TYPES: LeaveType[] = ["casual", "sick", "earned", "unpaid"];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function useStaff() {
  const { api } = useAppServices();
  const query = useQuery({ queryKey: ["users"], queryFn: () => api.getUsers() });
  const staff = query.data ?? [];
  const nameOf = (id: string) => staff.find((s) => s.id === id)?.username ?? id;
  return { staff, nameOf };
}

function StaffPicker({ staff, value, onChange }: { staff: StaffUser[]; value: string; onChange: (id: string) => void }) {
  const selected = staff.find((s) => s.id === value);
  return (
    <Dropdown value={selected?.username ?? ""} selectedOptions={value ? [value] : []} onOptionSelect={(_, d) => onChange(d.optionValue ?? "")}>
      {staff.map((s) => (
        <Option key={s.id} value={s.id} text={s.username}>
          {s.username} ({s.role})
        </Option>
      ))}
    </Dropdown>
  );
}

function AttendanceTab() {
  const { api } = useAppServices();
  const queryClient = useQueryClient();
  const { staff } = useStaff();
  const [workDate, setWorkDate] = useState(todayIso());
  const [error, setError] = useState<string | null>(null);

  const attendanceQuery = useQuery({
    queryKey: ["attendance", workDate],
    queryFn: () => api.listAttendance(workDate),
  });
  const records = attendanceQuery.data ?? [];

  const markMutation = useMutation({
    mutationFn: (payload: { user_id: string; status: AttendanceStatus }) =>
      api.markAttendance({ ...payload, work_date: workDate }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["attendance", workDate] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.detail : String(err)),
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Field label="Date" style={{ maxWidth: 220 }}>
        <Input type="date" value={workDate} onChange={(_, d) => setWorkDate(d.value)} />
      </Field>
      {error && <span style={{ color: "var(--colorPaletteRedForeground1)" }}>{error}</span>}
      <Table size="small">
        <TableHeader>
          <TableRow>
            <TableHeaderCell>Staff</TableHeaderCell>
            <TableHeaderCell>Role</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell>Mark</TableHeaderCell>
          </TableRow>
        </TableHeader>
        <TableBody>
          {staff.map((s) => {
            const record = records.find((r) => r.user_id === s.id);
            return (
              <TableRow key={s.id}>
                <TableCell>{s.username}</TableCell>
                <TableCell>{s.role}</TableCell>
                <TableCell>
                  {record ? (
                    <Badge appearance="tint" color={record.status === "absent" ? "danger" : record.status === "present" ? "success" : "warning"}>
                      {record.status.replace("_", " ")}
                    </Badge>
                  ) : (
                    <Badge appearance="tint" color="informative">
                      not marked
                    </Badge>
                  )}
                </TableCell>
                <TableCell>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {ATTENDANCE_STATUSES.map((opt) => (
                      <Button
                        key={opt.value}
                        size="small"
                        appearance={record?.status === opt.value ? "primary" : "secondary"}
                        disabled={markMutation.isPending}
                        onClick={() => markMutation.mutate({ user_id: s.id, status: opt.value })}
                      >
                        {opt.label}
                      </Button>
                    ))}
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {staff.length === 0 && <Body1Strong>No staff accounts yet.</Body1Strong>}
    </div>
  );
}

function LeaveTab() {
  const { api } = useAppServices();
  const queryClient = useQueryClient();
  const { staff, nameOf } = useStaff();
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [userId, setUserId] = useState("");
  const [leaveType, setLeaveType] = useState<LeaveType>("casual");
  const [startDate, setStartDate] = useState(todayIso());
  const [endDate, setEndDate] = useState(todayIso());
  const [reason, setReason] = useState("");

  const leaveQuery = useQuery({ queryKey: ["leave"], queryFn: () => api.listLeaveRequests() });
  const requests = leaveQuery.data ?? [];

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["leave"] });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createLeaveRequest({ user_id: userId, leave_type: leaveType, start_date: startDate, end_date: endDate, reason }),
    onSuccess: () => {
      setShowForm(false);
      setUserId("");
      setReason("");
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.detail : String(err)),
  });

  const decideMutation = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "approve" | "reject" }) =>
      api.decideLeaveRequest(id, decision),
    onSuccess: invalidate,
    onError: (err) => setError(err instanceof ApiError ? err.detail : String(err)),
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {error && <span style={{ color: "var(--colorPaletteRedForeground1)" }}>{error}</span>}
      <Button appearance="primary" style={{ alignSelf: "flex-start" }} onClick={() => setShowForm((v) => !v)}>
        {showForm ? "Cancel" : "Log leave"}
      </Button>
      {showForm && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
          <Field label="Staff">
            <StaffPicker staff={staff} value={userId} onChange={setUserId} />
          </Field>
          <Field label="Type">
            <Dropdown value={leaveType} selectedOptions={[leaveType]} onOptionSelect={(_, d) => setLeaveType((d.optionValue as LeaveType) ?? leaveType)}>
              {LEAVE_TYPES.map((t) => (
                <Option key={t} value={t}>
                  {t}
                </Option>
              ))}
            </Dropdown>
          </Field>
          <Field label="Start date">
            <Input type="date" value={startDate} onChange={(_, d) => setStartDate(d.value)} />
          </Field>
          <Field label="End date">
            <Input type="date" value={endDate} onChange={(_, d) => setEndDate(d.value)} />
          </Field>
          <Field label="Reason">
            <Input value={reason} onChange={(_, d) => setReason(d.value)} />
          </Field>
          <Button
            appearance="primary"
            disabled={!userId || !reason || createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            Submit
          </Button>
        </div>
      )}
      <Table size="small">
        <TableHeader>
          <TableRow>
            <TableHeaderCell>Staff</TableHeaderCell>
            <TableHeaderCell>Type</TableHeaderCell>
            <TableHeaderCell>Dates</TableHeaderCell>
            <TableHeaderCell>Days</TableHeaderCell>
            <TableHeaderCell>Reason</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell></TableHeaderCell>
          </TableRow>
        </TableHeader>
        <TableBody>
          {requests.map((r) => (
            <TableRow key={r.id}>
              <TableCell>{nameOf(r.user_id)}</TableCell>
              <TableCell>{r.leave_type}</TableCell>
              <TableCell>
                {r.start_date} → {r.end_date}
              </TableCell>
              <TableCell>{r.days_count}</TableCell>
              <TableCell>{r.reason}</TableCell>
              <TableCell>
                <Badge
                  appearance="tint"
                  color={r.status === "approved" ? "success" : r.status === "rejected" ? "danger" : "warning"}
                >
                  {r.status}
                </Badge>
              </TableCell>
              <TableCell>
                {r.status === "pending" && (
                  <div style={{ display: "flex", gap: 4 }}>
                    <Button size="small" onClick={() => decideMutation.mutate({ id: r.id, decision: "approve" })}>
                      Approve
                    </Button>
                    <Button size="small" onClick={() => decideMutation.mutate({ id: r.id, decision: "reject" })}>
                      Reject
                    </Button>
                  </div>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {requests.length === 0 && <Body1Strong>No leave requests yet.</Body1Strong>}
    </div>
  );
}

function TaDaTab() {
  const { api } = useAppServices();
  const queryClient = useQueryClient();
  const { staff, nameOf } = useStaff();
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [userId, setUserId] = useState("");
  const [claimDate, setClaimDate] = useState(todayIso());
  const [purpose, setPurpose] = useState("");
  const [fromLocation, setFromLocation] = useState("");
  const [toLocation, setToLocation] = useState("");
  const [travelMode, setTravelMode] = useState("");
  const [amountClaimed, setAmountClaimed] = useState("");

  const claimsQuery = useQuery({ queryKey: ["ta-da"], queryFn: () => api.listTaDaClaims() });
  const claims = claimsQuery.data ?? [];

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["ta-da"] });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createTaDaClaim({
        user_id: userId,
        claim_date: claimDate,
        purpose,
        from_location: fromLocation || null,
        to_location: toLocation || null,
        travel_mode: travelMode || null,
        amount_claimed: amountClaimed,
      }),
    onSuccess: () => {
      setShowForm(false);
      setUserId("");
      setPurpose("");
      setFromLocation("");
      setToLocation("");
      setTravelMode("");
      setAmountClaimed("");
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.detail : String(err)),
  });

  const decideMutation = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "approve" | "reject" }) => api.decideTaDaClaim(id, decision),
    onSuccess: invalidate,
    onError: (err) => setError(err instanceof ApiError ? err.detail : String(err)),
  });

  const payMutation = useMutation({
    mutationFn: (id: string) => api.markTaDaClaimPaid(id),
    onSuccess: invalidate,
    onError: (err) => setError(err instanceof ApiError ? err.detail : String(err)),
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {error && <span style={{ color: "var(--colorPaletteRedForeground1)" }}>{error}</span>}
      <Button appearance="primary" style={{ alignSelf: "flex-start" }} onClick={() => setShowForm((v) => !v)}>
        {showForm ? "Cancel" : "Log claim"}
      </Button>
      {showForm && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
          <Field label="Staff">
            <StaffPicker staff={staff} value={userId} onChange={setUserId} />
          </Field>
          <Field label="Date">
            <Input type="date" value={claimDate} onChange={(_, d) => setClaimDate(d.value)} />
          </Field>
          <Field label="Purpose">
            <Input value={purpose} onChange={(_, d) => setPurpose(d.value)} />
          </Field>
          <Field label="From">
            <Input value={fromLocation} onChange={(_, d) => setFromLocation(d.value)} />
          </Field>
          <Field label="To">
            <Input value={toLocation} onChange={(_, d) => setToLocation(d.value)} />
          </Field>
          <Field label="Mode">
            <Input value={travelMode} onChange={(_, d) => setTravelMode(d.value)} />
          </Field>
          <Field label="Amount claimed">
            <Input value={amountClaimed} onChange={(_, d) => setAmountClaimed(d.value)} type="number" />
          </Field>
          <Button
            appearance="primary"
            disabled={!userId || !purpose || !amountClaimed || createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            Submit
          </Button>
        </div>
      )}
      <Table size="small">
        <TableHeader>
          <TableRow>
            <TableHeaderCell>Staff</TableHeaderCell>
            <TableHeaderCell>Date</TableHeaderCell>
            <TableHeaderCell>Purpose</TableHeaderCell>
            <TableHeaderCell>Claimed</TableHeaderCell>
            <TableHeaderCell>Approved</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell></TableHeaderCell>
          </TableRow>
        </TableHeader>
        <TableBody>
          {claims.map((c) => (
            <TableRow key={c.id}>
              <TableCell>{nameOf(c.user_id)}</TableCell>
              <TableCell>{c.claim_date}</TableCell>
              <TableCell>{c.purpose}</TableCell>
              <TableCell>{c.amount_claimed}</TableCell>
              <TableCell>{c.amount_approved ?? "—"}</TableCell>
              <TableCell>
                <Badge
                  appearance="tint"
                  color={
                    c.status === "paid" ? "success" : c.status === "approved" ? "brand" : c.status === "rejected" ? "danger" : "warning"
                  }
                >
                  {c.status}
                </Badge>
              </TableCell>
              <TableCell>
                <div style={{ display: "flex", gap: 4 }}>
                  {c.status === "pending" && (
                    <>
                      <Button size="small" onClick={() => decideMutation.mutate({ id: c.id, decision: "approve" })}>
                        Approve
                      </Button>
                      <Button size="small" onClick={() => decideMutation.mutate({ id: c.id, decision: "reject" })}>
                        Reject
                      </Button>
                    </>
                  )}
                  {c.status === "approved" && (
                    <Button size="small" onClick={() => payMutation.mutate(c.id)}>
                      Mark paid
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {claims.length === 0 && <Body1Strong>No TA/DA claims yet.</Body1Strong>}
    </div>
  );
}

/** Admin-only HR module — Attendance/Leave/TA-DA (CLAUDE.md Section 12).
 * No employee self-service in v1: admin records everything on staff's
 * behalf. Each sub-tab gates on its own feature code so a tenant with only
 * one of the three overridden on still sees just that one. */
export default function HrAdmin() {
  const [tab, setTab] = useState<"attendance" | "leave" | "tada">("attendance");

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
      <Title2>HR</Title2>
      <TabList selectedValue={tab} onTabSelect={(_, data: SelectTabData) => setTab(data.value as typeof tab)}>
        <Tab value="attendance">Attendance</Tab>
        <Tab value="leave">Leave</Tab>
        <Tab value="tada">TA/DA</Tab>
      </TabList>
      {tab === "attendance" && (
        <FeatureGate feature="ATTENDANCE_TRACKING">
          <AttendanceTab />
        </FeatureGate>
      )}
      {tab === "leave" && (
        <FeatureGate feature="LEAVE_MANAGEMENT">
          <LeaveTab />
        </FeatureGate>
      )}
      {tab === "tada" && (
        <FeatureGate feature="TA_DA_CLAIMS">
          <TaDaTab />
        </FeatureGate>
      )}
    </div>
  );
}
