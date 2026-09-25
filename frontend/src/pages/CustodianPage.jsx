import DeviceRegistration from '../components/panels/DeviceRegistration';
import CustodianAssignments from '../components/panels/CustodianAssignments';
import SectionHeader from '../components/common/SectionHeader';

export default function CustodianPage() {
  return (
    <div className="dashboard">
      <SectionHeader title="Custodian" subtitle="Your assigned exam events and share submissions" />
      <DeviceRegistration />
      <CustodianAssignments />
    </div>
  );
}