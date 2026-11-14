import DeviceRegistration from '../components/panels/DeviceRegistration';
import CustodianAssignments from '../components/panels/CustodianAssignments';
import PageHeader from '../components/common/PageHeader';
import SectionHeader from '../components/common/SectionHeader';

export default function CustodianPage() {
  return (
    <div className="dashboard">
      <PageHeader title="Custodian" subtitle="Your assigned exam events and share submissions" />
      <DeviceRegistration />
      <SectionHeader title="Your Assignments" />
      <CustodianAssignments />
    </div>
  );
}